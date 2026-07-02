import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.agents.graph import investigation_graph
from backend.services.log_service import extract_log_content

router = APIRouter(prefix="/api", tags=["investigation"])

class InvestigationRequest(BaseModel):
    incident_description: str
    log_content: str = ""

@router.post("/investigation/run")
async def run_investigation(request: InvestigationRequest):
    """
    Runs the full multi-agent investigation pipeline.
    """
    investigation_id = str(uuid.uuid4())

    initial_state = {
        "incident_description": request.incident_description,
        "log_content": request.log_content,
        "evidence": [],
        "log_findings": {},
        "similar_incidents": [],
        "github_commits": [],
        "db_anomalies": [],
        "failed_tools": [],
        "completed_tools": [],
        "final_report": {},
        "investigation_id": investigation_id
    }

    try:
        final_state = await investigation_graph.ainvoke(initial_state)

        return {
            "investigation_id": investigation_id,
            "final_report": final_state["final_report"],
            "evidence_collected": final_state["evidence"],
            "tools_completed": final_state["completed_tools"],
            "tools_failed": final_state["failed_tools"],
            "similar_incidents_found": len(final_state["similar_incidents"])
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Investigation failed: {str(e)}"
        )