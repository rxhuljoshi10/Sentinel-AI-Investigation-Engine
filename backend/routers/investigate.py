import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import ValidationError
from backend.models.schemas import InvestigationReport
from backend.services.log_service import extract_log_content
from backend.services.llm_service import analyze_log

router = APIRouter(prefix="/api", tags=["investigate"])

@router.post("/investigate", response_model=InvestigationReport)
async def investigate_log(file: UploadFile = File(...)):
    """
    Accepts a log file upload and returns a structured investigation report.
    """

    # Step 1 — validate file type
    if not file.filename.endswith((".log", ".txt")):
        raise HTTPException(
            status_code=400,
            detail="Only .log and .txt files are supported"
        )

    # Step 2 — read and extract content
    raw_bytes = await file.read()
    log_content = extract_log_content(raw_bytes)

    # Step 3 — send to LLM
    raw_response = await analyze_log(log_content)

    # Step 4 — parse JSON
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"LLM returned invalid JSON: {raw_response[:200]}"
        )

    # Step 5 — validate with Pydantic
    try:
        report = InvestigationReport(**parsed)
    except ValidationError as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM response failed validation: {e.errors()}"
        )

    return report