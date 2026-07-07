from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.models.schemas import ChatRequest
from backend.services.llm_service import stream_investigation
from backend.core.auth import get_current_user
from fastapi import Depends

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Accepts an incident description and streams back an AI investigation.
    """
    return StreamingResponse(
        stream_investigation(request.message),
        media_type="text/plain"
    )