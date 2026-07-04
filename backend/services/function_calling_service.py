import httpx
import json
from backend.core.config import settings
from backend.tools.registry import TOOL_DEFINITIONS, execute_tool

async def run_function_calling(
    incident_description: str,
    log_content: str
) -> dict:
    """
    Lets the LLM decide which tools to call based on the incident.
    Executes chosen tools and returns all results.
    """

    # Step 1 — Ask LLM which tools to use
    tool_selection_prompt = f"""You are an incident investigation planner.
Given this incident, decide which tools to call to gather evidence.
You must respond with ONLY a JSON object, no markdown.

Available tools and when to use them:
{json.dumps(TOOL_DEFINITIONS, indent=2)}

Respond with exactly this format:
{{
    "reasoning": "one sentence explaining your tool choices",
    "tools_to_call": [
        {{
            "name": "tool_name",
            "arguments": {{"arg1": "value1"}}
        }}
    ]
}}

Incident: {incident_description}
Log preview: {log_content[:300] if log_content else "No log provided"}"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert incident investigator. Respond only with valid JSON."
                        },
                        {
                            "role": "user",
                            "content": tool_selection_prompt
                        }
                    ],
                    "stream": False,
                    "options": {
                        "num_predict": 400,
                        "temperature": 0.2,
                        "num_ctx": 2048
                    }
                }
            )
            raw = response.json()["message"]["content"].strip()

            # Clean JSON
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            start = raw.find("{")
            end = raw.rfind("}") + 1
            selection = json.loads(raw[start:end])

    except Exception as e:
        print(f"[Function Calling] Tool selection failed: {e}")
        # Default to GitHub + DB if LLM fails
        selection = {
            "reasoning": "Defaulting to standard tools",
            "tools_to_call": [
                {"name": "search_github_commits",
                 "arguments": {"service": "unknown", "hours_before_incident": 24}},
                {"name": "query_incidents_db",
                 "arguments": {"service": "unknown"}}
            ]
        }

    print(f"[Function Calling] Reasoning: {selection.get('reasoning')}")
    print(f"[Function Calling] Tools selected: {[t['name'] for t in selection.get('tools_to_call', [])]}")

    # Step 2 — Execute selected tools
    tool_results = {}
    for tool_call in selection.get("tools_to_call", []):
        tool_name = tool_call["name"]
        arguments = tool_call.get("arguments", {})

        print(f"[Function Calling] Executing: {tool_name}({arguments})")
        result = await execute_tool(tool_name, arguments)
        tool_results[tool_name] = result
        print(f"[Function Calling] {tool_name} success: {result.get('success')}")

    return {
        "reasoning": selection.get("reasoning", ""),
        "tools_called": list(tool_results.keys()),
        "results": tool_results
    }