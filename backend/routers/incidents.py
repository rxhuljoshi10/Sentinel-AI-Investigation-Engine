import json
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import ValidationError
from backend.models.schemas import (
    InvestigationReport,
    EnrichedReport
)
from backend.services.log_service import extract_log_content
from backend.services.llm_service import analyze_log_with_context
from backend.services.vector_service import (
    store_incident,
    search_similar_incidents
)

router = APIRouter(prefix="/api", tags=["incidents"])

@router.post("/incidents/investigate", response_model=EnrichedReport)
async def investigate_with_context(file: UploadFile = File(...)):
    """
    Investigates a log file using RAG — retrieves similar past incidents
    and uses them as context for a richer investigation.
    """

    if not file.filename.endswith((".log", ".txt")):
        raise HTTPException(
            status_code=400,
            detail="Only .log and .txt files are supported"
        )

    # Step 1 — extract log content
    raw_bytes = await file.read()
    log_content = extract_log_content(raw_bytes)

    # Step 2 — quick first-pass analysis to understand what we're dealing with
    raw_response = await analyze_log_with_context(log_content, [])

    try:
        parsed = json.loads(raw_response)
        report = InvestigationReport(**parsed)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Step 3 — search for similar past incidents
    similar_incidents = await search_similar_incidents(log_content, report)

    # Step 4 — if we found similar incidents, re-analyze with context
    if similar_incidents:
        raw_response = await analyze_log_with_context(
            log_content,
            similar_incidents
        )
        try:
            parsed = json.loads(raw_response)
            report = InvestigationReport(**parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Step 5 — store this incident for future searches
    incident_id = str(uuid.uuid4())
    await store_incident(incident_id, log_content, report)

    return EnrichedReport(
        report=report,
        similar_incidents=similar_incidents,
        context_used=len(similar_incidents) > 0
    )