from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.models.schemas import ChatRequest
from backend.services.llm_service import stream_investigation

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Accepts an incident description and streams back an AI investigation.
    """
    return StreamingResponse(
        stream_investigation(request.message),
        media_type="text/plain"
    )