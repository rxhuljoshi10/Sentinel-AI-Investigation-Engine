import uuid
from datetime import datetime
from sqlalchemy import text
from backend.core.database import AsyncSessionLocal
import json

async def get_service_memory(service_name: str) -> dict:
    """
    Retrieves accumulated memory for a specific service.
    Returns patterns, common fixes, and runbooks.
    """
    async with AsyncSessionLocal() as session:
        # Get service memory
        result = await session.execute(
            text("""
                SELECT * FROM service_memory 
                WHERE service_name ILIKE :service
            """),
            {"service": f"%{service_name}%"}
        )
        memory = result.mappings().first()

        # Get relevant runbooks
        runbooks = await session.execute(
            text("""
                SELECT * FROM runbooks
                WHERE service_name ILIKE :service
                ORDER BY confidence DESC, times_used DESC
                LIMIT 3
            """),
            {"service": f"%{service_name}%"}
        )
        runbook_rows = runbooks.mappings().all()

        if not memory:
            return {
                "service": service_name,
                "has_memory": False,
                "total_incidents": 0,
                "common_causes": [],
                "successful_fixes": [],
                "runbooks": []
            }

        return {
            "service": service_name,
            "has_memory": True,
            "total_incidents": memory["total_incidents"],
            "common_causes": memory["common_causes"] or [],
            "successful_fixes": memory["successful_fixes"] or [],
            "peak_times": memory["peak_incident_times"] or [],
            "runbooks": [
                {
                    "trigger": r["trigger_pattern"],
                    "steps": r["resolution_steps"],
                    "confidence": r["confidence"],
                    "times_used": r["times_used"]
                }
                for r in runbook_rows
            ]
        }

async def update_service_memory(
    service_name: str,
    probable_cause: str,
    immediate_actions: list,
    confidence: float
) -> None:
    """
    Updates service memory after a completed investigation.
    Learns from each investigation incrementally.
    """
    async with AsyncSessionLocal() as session:
        # Check if memory exists for this service
        result = await session.execute(
            text("SELECT * FROM service_memory WHERE service_name = :service"),
            {"service": service_name}
        )
        existing = result.mappings().first()

        if existing:
            # Update existing memory
            current_causes = existing["common_causes"] or []
            current_fixes = existing["successful_fixes"] or []

            # Add new cause if not already known
            if probable_cause not in current_causes:
                current_causes.append(probable_cause)
                # Keep only top 10 most recent causes
                current_causes = current_causes[-10:]

            # Add new fixes if not already known
            for action in immediate_actions:
                if action not in current_fixes:
                    current_fixes.append(action)
            current_fixes = current_fixes[-20:]

            await session.execute(
                text("""
                    UPDATE service_memory
                    SET total_incidents = total_incidents + 1,
                        common_causes = :causes,
                        successful_fixes = :fixes,
                        last_updated = NOW()
                    WHERE service_name = :service
                """),
                {
                    "service": service_name,
                    "causes": json.dumps(current_causes),
                    "fixes": json.dumps(current_fixes)
                }
            )
        else:
            # Create new memory for this service
            await session.execute(
                text("""
                    INSERT INTO service_memory (
                        id, service_name, total_incidents,
                        common_causes, successful_fixes,
                        peak_incident_times, last_updated
                    ) VALUES (
                        :id, :service, 1,
                        :causes, :fixes, :times, NOW()
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "service": service_name,
                    "causes": json.dumps([probable_cause]),
                    "fixes": json.dumps(immediate_actions),
                    "times": json.dumps([])
                }
            )

        # Create a runbook if confidence is high enough
        if confidence >= 0.85:
            await session.execute(
                text("""
                    INSERT INTO runbooks (
                        id, service_name, trigger_pattern,
                        resolution_steps, confidence,
                        times_used, created_at, last_used
                    ) VALUES (
                        :id, :service, :trigger,
                        :steps, :confidence, 1, NOW(), NOW()
                    )
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "service": service_name,
                    "trigger": probable_cause,
                    "steps": json.dumps(immediate_actions),
                    "confidence": confidence
                }
            )

        await session.commit()
        print(f"[Memory] Updated memory for {service_name}")