from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    model: str

class InvestigationReport(BaseModel):
    severity: str
    affected_service: str
    probable_cause: str
    evidence: list[str]
    immediate_actions: list[str]
    confidence: float

    # Extended RCA fields (optional for backward compatibility)
    root_cause_category: Optional[str] = None
    impact: Optional[str] = None
    long_term_prevention: Optional[list[str]] = None
    escalation: Optional[str] = None
    investigation_summary: Optional[str] = None

    @field_validator("severity")
    @classmethod
    def severity_must_be_valid(cls, v):
        allowed = {"critical", "high", "medium", "low", "unknown"}
        if v.lower() not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v.lower()

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_valid(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v

# NEW models below

class StoredIncident(BaseModel):
    id: str
    log_content: str
    report: InvestigationReport
    created_at: datetime

class SimilarIncident(BaseModel):
    id: str
    similarity_score: float
    affected_service: str
    probable_cause: str
    immediate_actions: list[str]
    created_at: datetime

class EnrichedReport(BaseModel):
    report: InvestigationReport
    similar_incidents: list[SimilarIncident]
    context_used: bool