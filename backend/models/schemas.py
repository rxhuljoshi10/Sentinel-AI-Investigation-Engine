from pydantic import BaseModel, field_validator

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    model: str

class InvestigationReport(BaseModel):
    severity: str                    # critical / high / medium / low
    affected_service: str            # which service is broken
    probable_cause: str              # root cause hypothesis
    evidence: list[str]              # log lines that support the finding
    immediate_actions: list[str]     # what to do right now
    confidence: float                # 0.0 to 1.0

    @field_validator("severity")
    @classmethod
    def severity_must_be_valid(cls, v):
        allowed = {"critical", "high", "medium", "low"}
        if v.lower() not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v.lower()

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_valid(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v