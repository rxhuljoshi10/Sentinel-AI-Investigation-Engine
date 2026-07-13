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


# ─── History Endpoints ────────────────────────────────────────────────────────

@router.get("/investigations")
async def list_investigations(
    severity: str | None = None,
    service: str | None = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns a paginated list of past investigations from PostgreSQL,
    sorted newest first. Optionally filter by severity and/or service.
    """
    from sqlalchemy import select, desc
    from backend.core.database import AsyncSessionLocal, IncidentRecord

    async with AsyncSessionLocal() as session:
        query = select(
            IncidentRecord.id,
            IncidentRecord.description,
            IncidentRecord.severity,
            IncidentRecord.affected_service,
            IncidentRecord.probable_cause,
            IncidentRecord.confidence,
            IncidentRecord.tools_completed,
            IncidentRecord.tools_failed,
            IncidentRecord.created_at
        ).order_by(desc(IncidentRecord.created_at)).limit(100)

        if severity and severity != "all":
            query = query.where(IncidentRecord.severity == severity)
        if service and service != "all":
            query = query.where(IncidentRecord.affected_service == service)

        result = await session.execute(query)
        rows = result.all()

    return [
        {
            "id": r.id,
            "description": r.description,
            "severity": r.severity,
            "affected_service": r.affected_service,
            "probable_cause": r.probable_cause,
            "confidence": r.confidence,
            "tools_completed": r.tools_completed or [],
            "tools_failed": r.tools_failed or [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/investigations/frequency")
async def get_investigation_frequency(current_user: dict = Depends(get_current_user)):
    """
    Returns daily incident counts for the last 30 days.
    Used to power the frequency bar chart on the history page.
    """
    from sqlalchemy import select
    from backend.core.database import AsyncSessionLocal, IncidentRecord
    from datetime import datetime, timedelta
    from collections import defaultdict

    since = datetime.utcnow() - timedelta(days=30)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IncidentRecord.created_at, IncidentRecord.severity)
            .where(IncidentRecord.created_at >= since)
            .order_by(IncidentRecord.created_at)
        )
        rows = result.all()

    # Group by date string
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.created_at:
            date_str = r.created_at.strftime("%Y-%m-%d")
            counts[date_str] += 1

    # Fill in zeros for dates with no incidents (last 30 days)
    all_dates = []
    for i in range(30):
        d = (datetime.utcnow() - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        all_dates.append({"date": d, "count": counts.get(d, 0)})

    return all_dates


@router.get("/investigations/{investigation_id}")
async def get_investigation_detail(
    investigation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the full stored detail of a single past investigation.
    """
    from sqlalchemy import select
    from backend.core.database import AsyncSessionLocal, IncidentRecord

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IncidentRecord).where(IncidentRecord.id == investigation_id)
        )
        record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return {
        "id": record.id,
        "description": record.description,
        "log_content": record.log_content,
        "severity": record.severity,
        "affected_service": record.affected_service,
        "probable_cause": record.probable_cause,
        "evidence": record.evidence or [],
        "immediate_actions": record.immediate_actions or [],
        "confidence": record.confidence,
        "investigation_summary": record.investigation_summary,
        "tools_completed": record.tools_completed or [],
        "tools_failed": record.tools_failed or [],
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
