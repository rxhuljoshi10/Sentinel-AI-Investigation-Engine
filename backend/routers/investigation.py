import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.agents.graph import investigation_graph
from backend.tools.database_tool import save_incident_to_db
from backend.services.memory_service import update_service_memory

router = APIRouter(prefix="/api", tags=["investigation"])

class InvestigationRequest(BaseModel):
    incident_description: str
    log_content: str = ""

@router.post("/investigation/run")
async def run_investigation(request: InvestigationRequest):
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

        # Save to PostgreSQL
        await save_incident_to_db(
            investigation_id=investigation_id,
            description=request.incident_description,
            log_content=request.log_content,
            final_report=final_state["final_report"],
            tools_completed=final_state["completed_tools"],
            tools_failed=final_state["failed_tools"]
        )
        print(f"[Investigation] Saved to PostgreSQL: {investigation_id}")

         # Update memory with findings
        final_report = final_state["final_report"]
        if final_report.get("affected_service", "unknown") != "unknown":
            await update_service_memory(
                service_name=final_report["affected_service"],
                probable_cause=final_report.get("probable_cause", ""),
                immediate_actions=final_report.get("immediate_actions", []),
                confidence=final_report.get("confidence", 0.0)
            )

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