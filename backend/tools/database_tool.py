from sqlalchemy import text
from backend.core.database import AsyncSessionLocal

async def query_incidents_db(
    service: str,
    limit: int = 5
) -> dict:
    """
    Queries PostgreSQL for past incidents related to a service.
    Returns recent incidents, severity patterns, and resolution history.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        id,
                        affected_service,
                        severity,
                        probable_cause,
                        immediate_actions,
                        confidence,
                        created_at
                    FROM incidents
                    WHERE affected_service ILIKE :service
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"service": f"%{service}%", "limit": limit}
            )
            rows = result.mappings().all()

            incidents = []
            for row in rows:
                incidents.append({
                    "id": row["id"],
                    "service": row["affected_service"],
                    "severity": row["severity"],
                    "probable_cause": row["probable_cause"],
                    "immediate_actions": row["immediate_actions"],
                    "confidence": row["confidence"],
                    "created_at": str(row["created_at"])
                })

            return {
                "success": True,
                "incidents_found": len(incidents),
                "incidents": incidents,
                "queried_service": service
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "incidents": []
        }

async def save_incident_to_db(
    investigation_id: str,
    description: str,
    log_content: str,
    final_report: dict,
    tools_completed: list,
    tools_failed: list
) -> bool:
    """
    Saves a completed investigation to PostgreSQL.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO incidents (
                        id, description, log_content,
                        severity, affected_service, probable_cause,
                        evidence, immediate_actions, confidence,
                        investigation_summary, tools_completed,
                        tools_failed, created_at
                    ) VALUES (
                        :id, :description, :log_content,
                        :severity, :affected_service, :probable_cause,
                        :evidence, :immediate_actions, :confidence,
                        :investigation_summary, :tools_completed,
                        :tools_failed, NOW()
                    )
                """),
                {
                    "id": investigation_id,
                    "description": description,
                    "log_content": log_content[:2000],
                    "severity": final_report.get("severity", "unknown"),
                    "affected_service": final_report.get("affected_service", "unknown"),
                    "probable_cause": final_report.get("probable_cause", ""),
                    "evidence": str(final_report.get("evidence", [])),
                    "immediate_actions": str(final_report.get("immediate_actions", [])),
                    "confidence": final_report.get("confidence", 0.0),
                    "investigation_summary": final_report.get("investigation_summary", ""),
                    "tools_completed": str(tools_completed),
                    "tools_failed": str(tools_failed)
                }
            )
            await session.commit()
            return True

    except Exception as e:
        print(f"[DB] Failed to save incident: {e}")
        return False