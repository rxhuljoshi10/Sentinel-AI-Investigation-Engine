from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, String, Float, DateTime, Text, JSON, Integer
from datetime import datetime
from backend.core.config import settings


engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

class IncidentRecord(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True)
    description = Column(Text, nullable=False)
    log_content = Column(Text)
    severity = Column(String)
    affected_service = Column(String)
    probable_cause = Column(Text)
    evidence = Column(JSON)
    immediate_actions = Column(JSON)
    confidence = Column(Float)
    investigation_summary = Column(Text)
    tools_completed = Column(JSON)
    tools_failed = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class ToolCallRecord(Base):
    __tablename__ = "tool_calls"

    id = Column(String, primary_key=True)
    investigation_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(JSON)
    result_summary = Column(Text)
    success = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class ServiceMemory(Base):
    __tablename__ = "service_memory"

    id = Column(String, primary_key=True)
    service_name = Column(String, nullable=False, unique=True)
    total_incidents = Column(Integer, default=0)
    common_causes = Column(JSON)        # list of frequent causes
    successful_fixes = Column(JSON)     # list of fixes that worked
    peak_incident_times = Column(JSON)  # when incidents usually happen
    last_updated = Column(DateTime, default=datetime.utcnow)

class InvestigationRunbook(Base):
    __tablename__ = "runbooks"

    id = Column(String, primary_key=True)
    service_name = Column(String, nullable=False)
    trigger_pattern = Column(Text)      # what triggers this runbook
    resolution_steps = Column(JSON)     # proven fix steps
    confidence = Column(Float)          # how reliable this runbook is
    times_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()