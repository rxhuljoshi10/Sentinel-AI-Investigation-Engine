import httpx
import json
from backend.core.config import settings
from backend.core.cache import get_cached, set_cached, make_cache_key

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

async def analyze_log(log_content: str) -> dict:
    """
    Sends log content to Ollama and returns a structured investigation report.
    """

    cache_key = make_cache_key("log_analysis", log_content)
    cached = await get_cached(cache_key)
    if cached:
        print("[LLM] Cache hit — returning cached analysis")
        return cached

    system_prompt = """You are Sentinel, an expert incident investigation AI.
Analyze the provided log content and respond with ONLY a valid JSON object.
No explanation. No markdown. No code blocks. Raw JSON only.

You must use exactly these keys:
- severity: one of "critical", "high", "medium", "low"
- affected_service: name of the service or component causing the issue
- probable_cause: one clear sentence describing the root cause
- evidence: list of 2-4 specific log lines or patterns that support your finding
- immediate_actions: list of 2-4 concrete steps to resolve the issue
- confidence: float between 0.0 and 1.0 representing your confidence

Example format:
{
  "severity": "critical",
  "affected_service": "payment-service",
  "probable_cause": "Database connection pool exhausted due to connection leak",
  "evidence": [
    "ERROR: Connection pool timeout after 30000ms",
    "WARN: Active connections: 100/100"
  ],
  "immediate_actions": [
    "Restart the payment service to release connections",
    "Increase connection pool size in application config"
  ],
  "confidence": 0.85
}"""

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this log:\n\n{log_content}"}
        ],
        "stream": False,
        "options": {
            "num_predict": 500,
            "temperature": 0.3,
            "num_ctx": 2048
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        content = data["message"]["content"].strip()

        await set_cached(cache_key, content, ttl=3600)

        return content                    
    
async def analyze_log_with_context(
    log_content: str,
    similar_incidents: list
) -> dict:
    """
    Analyzes a log file with context from similar past incidents.
    """

    # Build context block from similar incidents
    context_block = ""
    if similar_incidents:
        context_block = "\n\nRELEVANT PAST INCIDENTS FOR CONTEXT:\n"
        for i, incident in enumerate(similar_incidents, 1):
            context_block += f"""
Incident {i} (similarity: {incident.similarity_score}):
- Service: {incident.affected_service}
- Root cause: {incident.probable_cause}
- How it was resolved: {", ".join(incident.immediate_actions)}
"""

    system_prompt = """You are Sentinel, an expert incident investigation AI.
Analyze the provided log content and respond with ONLY a valid JSON object.
No explanation. No markdown. No code blocks. Raw JSON only.

If past incidents are provided, use them to inform your analysis.
Similar past incidents suggest patterns worth investigating.

You must use exactly these keys:
- severity: one of "critical", "high", "medium", "low"
- affected_service: name of the service or component causing the issue
- probable_cause: one clear sentence describing the root cause
- evidence: list of 2-4 specific log lines or patterns that support your finding
- immediate_actions: list of 2-4 concrete steps to resolve the issue
- confidence: float between 0.0 and 1.0 representing your confidence"""

    user_message = f"Analyze this log:{context_block}\n\nCURRENT LOG:\n{log_content}"

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "stream": False,
        "options": {
            "num_predict": 500,
            "temperature": 0.3,
            "num_ctx": 2048
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()