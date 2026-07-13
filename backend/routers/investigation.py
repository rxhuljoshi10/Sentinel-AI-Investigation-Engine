import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.agents.graph import investigation_graph
from backend.tools.database_tool import save_incident_to_db
from backend.services.memory_service import update_service_memory
from backend.core.auth import get_current_user
import asyncio
import json

router = APIRouter(prefix="/api", tags=["investigation"])

class InvestigationRequest(BaseModel):
    incident_description: str
    log_content: str = ""

@router.post("/investigation/run")
async def run_investigation(request: InvestigationRequest, current_user: dict = Depends(get_current_user)):
    investigation_id = str(uuid.uuid4())

    initial_state = {
        "incident_description": request.incident_description,
        "log_content": request.log_content,
        "evidence": [],
        "log_findings": {},
        "similar_incidents": [],
        "github_commits": [],
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

@router.post("/investigation/run-stream")
async def run_investigation_stream(request: InvestigationRequest, current_user: dict = Depends(get_current_user)):
    investigation_id = str(uuid.uuid4())
    queue = asyncio.Queue()

    initial_state = {
        "incident_description": request.incident_description,
        "log_content": request.log_content,
        "evidence": [],
        "log_findings": {},
        "similar_incidents": [],
        "github_commits": [],
        "failed_tools": [],
        "completed_tools": [],
        "final_report": {},
        "investigation_id": investigation_id,
        "progress_queue": queue
    }

    # Start graph run in background
    task = asyncio.create_task(investigation_graph.ainvoke(initial_state))

    async def event_generator():
        try:
            while not task.done() or not queue.empty():
                try:
                    # Get logs from queue
                    log_item = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield f"event: progress\ndata: {json.dumps(log_item)}\n\n"
                    queue.task_done()
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue

            # Graph is done. Await result or handle failure
            final_state = await task
            final_report = final_state["final_report"]

            # Save to PostgreSQL
            await save_incident_to_db(
                investigation_id=investigation_id,
                description=request.incident_description,
                log_content=request.log_content,
                final_report=final_report,
                tools_completed=final_state["completed_tools"],
                tools_failed=final_state["failed_tools"]
            )

            # Update memory with findings
            if final_report.get("affected_service", "unknown") != "unknown":
                await update_service_memory(
                    service_name=final_report["affected_service"],
                    probable_cause=final_report.get("probable_cause", ""),
                    immediate_actions=final_report.get("immediate_actions", []),
                    confidence=final_report.get("confidence", 0.0)
                )

            # Package and yield final result
            result = {
                "investigation_id": investigation_id,
                "final_report": final_report,
                "evidence_collected": final_state["evidence"],
                "tools_completed": final_state["completed_tools"],
                "tools_failed": final_state["failed_tools"],
                "similar_incidents_found": len(final_state["similar_incidents"])
            }
            yield f"event: result\ndata: {json.dumps(result)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/investigation/cache-stats")
async def get_cache_stats_endpoint(current_user: dict = Depends(get_current_user)):
    from backend.core.cache import get_cache_stats
    stats = await get_cache_stats()
    return stats