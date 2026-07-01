import httpx
import json
from backend.core.config import settings

async def stream_investigation(message: str):
    """
    Sends a message to Ollama and streams the response back token by token.
    """

    system_prompt = """You are Sentinel, an expert AI system specialized in 
    investigating software engineering incidents. When given an incident description,
    you analyze symptoms, identify probable root causes, assess impact, and suggest
    immediate remediation steps. Be precise, structured, and technical."""

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "stream": True,
        "options": {
            "num_predict": 250,
            "temperature": 0.7,
            "num_ctx": 2048
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue