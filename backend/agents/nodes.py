import httpx
import json
from backend.core.config import settings
from backend.agents.state import InvestigationState
from backend.services.vector_service import search_similar_incidents
from backend.models.schemas import InvestigationReport
from backend.services.function_calling_service import run_function_calling
# from backend.tools.database_tool import save_incident_to_db
from backend.services.memory_service import get_service_memory, update_service_memory
import os

def clean_and_parse_json(raw: str) -> dict:
    """
    Cleans LLM output and attempts to parse as JSON.
    Handles markdown code blocks, extra text, and empty responses.
    """
    if not raw or not raw.strip():
        raise ValueError("LLM returned empty response")

    cleaned = raw.strip()

    # Remove markdown code blocks if present
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    # Find JSON object boundaries in case there's text before/after
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in response: {cleaned[:100]}")

    cleaned = cleaned[start:end]
    return json.loads(cleaned)

async def call_llm_with_retry(messages: list, max_retries: int = 3) -> dict:
    """
    Calls Ollama with retry logic. Returns parsed JSON.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "num_predict": 500,
                            "temperature": 0.2,
                            "num_ctx": 2048
                        }
                    }
                )
                content = response.json()["message"]["content"].strip()
                return clean_and_parse_json(content)

        except Exception as e:
            last_error = e
            print(f"  Attempt {attempt + 1}/{max_retries} failed: {e}")

    raise last_error


# ─── Planner Node ────────────────────────────────────────────────────────────
async def planner_node(state: InvestigationState) -> dict:
    print(f"[Planner] Starting investigation: {state['incident_description'][:100]}")

    # Run function calling — LLM decides which tools to use
    fc_results = await run_function_calling(
        state["incident_description"],
        state.get("log_content", "")
    )

    # Convert tool results into evidence
    evidence_items = [
        f"Investigation started: {state['incident_description']}",
        f"Tool selection reasoning: {fc_results['reasoning']}"
    ]

    # Extract evidence from each tool result
    for tool_name, result in fc_results["results"].items():
        if not result.get("success"):
            evidence_items.append(f"{tool_name} failed: {result.get('error')}")
            continue

        if tool_name == "search_github_commits":
            commits = result.get("commits", [])
            is_simulated = result.get("simulated", False)
            prefix = "[SIMULATED COMMIT]" if is_simulated else "[GITHUB COMMIT]"
            for commit in commits[:3]:
                evidence_items.append(
                    f"{prefix} '{commit['message']}' "
                    f"by {commit['author']} at {commit['timestamp']}"
                )

        elif tool_name == "query_incidents_db":
            incidents = result.get("incidents", [])
            for inc in incidents[:3]:
                evidence_items.append(
                    f"Past DB incident: {inc['probable_cause']} "
                    f"(severity: {inc['severity']})"
                )

        elif tool_name == "read_log_file":
            content = result.get("content", "")
            if content:
                evidence_items.append(
                    f"Log file content preview: {content[:200]}"
                )

    print(f"[Planner] Collected {len(evidence_items)} items from tools")

    return {
        "evidence": evidence_items,
        "completed_tools": ["planner"],
        "github_commits": fc_results["results"].get(
            "search_github_commits", {}
        ).get("commits", [])
    }

# ─── Log Analyzer Node ───────────────────────────────────────────────────────
async def log_analyzer_node(state: InvestigationState) -> dict:
    print("[Log Analyzer] Analyzing log content...")

    log_content = state.get("log_content", "")
    if not log_content:
        print("[Log Analyzer] No log content, skipping")
        return {"failed_tools": ["log_analyzer"], "log_findings": {}}

    try:
        findings = await call_llm_with_retry([
            {
                "role": "system",
                "content": "You are a log analysis expert. Respond only with valid JSON, no markdown."
            },
            {
                "role": "user",
                "content": f"""Analyze this log. Reply with ONLY a JSON object.

Required keys:
- error_patterns: list of error types found (strings)
- timeline: when issues started (string)
- affected_components: list of service names (strings)
- severity_indicators: list of critical log lines (strings)

LOG:
{log_content[:1000]}"""
            }
        ])

        evidence_items = [
            f"[CURRENT LOG] Timeline: {findings.get('timeline', 'unknown')}",
            f"[CURRENT LOG] Affected: {', '.join(findings.get('affected_components', []))}",
        ]
        for pattern in findings.get("error_patterns", [])[:3]:
            evidence_items.append(f"[CURRENT LOG] Pattern: {pattern}")

        print(f"[Log Analyzer] Found {len(evidence_items)} evidence items")
        return {
            "log_findings": findings,
            "evidence": evidence_items,
            "completed_tools": ["log_analyzer"]
        }

    except Exception as e:
        print(f"[Log Analyzer] Failed after retries: {e}")
        return {"failed_tools": ["log_analyzer"], "log_findings": {}}
    

# ─── RAG Searcher Node ───────────────────────────────────────────────────────
async def rag_searcher_node(state: InvestigationState) -> dict:
    """
    Searches ChromaDB for similar past incidents.
    """
    print("[RAG Searcher] Searching for similar incidents...")

    try:
        log_findings = state.get("log_findings", {})

        # Build a temporary report object for the search
        temp_report = InvestigationReport(
            severity="high",
            affected_service=", ".join(
                log_findings.get("affected_components", ["unknown"])
            ),
            probable_cause=state["incident_description"],
            evidence=log_findings.get("severity_indicators", [])[:2] or ["none"],
            immediate_actions=["investigating"],
            confidence=0.5
        )

        similar = await search_similar_incidents(
            state.get("log_content", state["incident_description"]),
            temp_report,
            top_k=3
        )

        evidence_items = []
        for incident in similar:
            evidence_items.append(
                f"[PAST INCIDENT] Similar (score: {incident.similarity_score}): "
                f"{incident.probable_cause}"
                f"{incident.immediate_actions[0] if incident.immediate_actions else 'unknown'}"
            )

        print(f"[RAG Searcher] Found {len(similar)} similar incidents")

        return {
            "similar_incidents": similar,
            "evidence": evidence_items,
            "completed_tools": ["rag_searcher"]
        }

    except Exception as e:
        print(f"[RAG Searcher] Failed: {e}")
        return {
            "failed_tools": ["rag_searcher"],
            "similar_incidents": []
        }


async def reasoner_node(state: InvestigationState) -> dict:
    from backend.core.cache import get_cached, set_cached, make_cache_key

    incident_desc = state.get("incident_description", "")
    log_content = state.get("log_content", "")
    combined_content = f"{incident_desc}|||{log_content}"
    cache_key = make_cache_key("reasoner_report", combined_content)

    cached_report = await get_cached(cache_key)
    if cached_report:
        print("[Reasoner] Cache hit — returning cached report")
        return {"final_report": cached_report}

    print(f"[Reasoner] Synthesizing {len(state.get('evidence', []))} evidence items...")

    all_evidence = state.get("evidence", [])

    # Separate current log evidence from historical context
    current_evidence = [e for e in all_evidence if e.startswith("[CURRENT LOG]")]
    historical_evidence = [e for e in all_evidence if e.startswith("[PAST INCIDENT]") or e.startswith("[MEMORY]")]
    other_evidence = [e for e in all_evidence if not e.startswith("[CURRENT LOG]") and not e.startswith("[PAST") and not e.startswith("[MEMORY]")]

    current_block = "\n".join(f"- {e}" for e in current_evidence)
    historical_block = "\n".join(f"- {e}" for e in historical_evidence)
    other_block = "\n".join(f"- {e}" for e in other_evidence)

    completed = state.get("completed_tools", [])
    failed = state.get("failed_tools", [])

    try:
        report = await call_llm_with_retry([
            {
                "role": "system",
                "content": "You are an expert incident investigator. Respond only with valid JSON, no markdown."
            },
            {
                "role": "user",
                "content": f"""Investigate this incident. Reply with ONLY a JSON object.

CURRENT INCIDENT: {state['incident_description']}

CURRENT LOG EVIDENCE (use this as primary source):
{current_block if current_block else "No log evidence available"}

HISTORICAL CONTEXT (reference only, do NOT copy these conclusions):
{historical_block if historical_block else "No historical context"}

OTHER EVIDENCE:
{other_block if other_block else "None"}

Required JSON keys:
- severity: "critical", "high", "medium", or "low"
- affected_service: service name from CURRENT LOG
- probable_cause: root cause based on CURRENT LOG evidence
- evidence: list of 3 items FROM CURRENT LOG only
- immediate_actions: list of 3 fix steps for THIS specific issue
- confidence: number 0.0 to 1.0
- investigation_summary: two sentences about THIS incident"""
            }
        ])

        print("[Reasoner] Report generated successfully")
        await set_cached(cache_key, report, ttl=3600)
        return {"final_report": report}

    except Exception as e:
        print(f"[Reasoner] Failed after retries: {e}")
        return {
            "final_report": {
                "severity": "unknown",
                "affected_service": "unknown",
                "probable_cause": f"Reasoner failed: {str(e)}",
                "evidence": current_evidence[:3],
                "immediate_actions": ["Manual investigation required"],
                "confidence": 0.0,
                "investigation_summary": "Automated investigation failed."
            }
        }
    
#Memory Node
async def memory_node(state: InvestigationState) -> dict:
    """
    Two responsibilities:
    1. Before investigation — retrieve relevant memory
    2. After investigation — update memory with new findings
    """
    if os.environ.get("EVAL_MODE") == "true":
        return {"completed_tools": ["memory"]}
    print("[Memory] Retrieving service memory...")

    final_report = state.get("final_report", {})
    affected_service = final_report.get("affected_service", "")

    # If we have a final report, update memory
    if affected_service and affected_service != "unknown":
        await update_service_memory(
            service_name=affected_service,
            probable_cause=final_report.get("probable_cause", ""),
            immediate_actions=final_report.get("immediate_actions", []),
            confidence=final_report.get("confidence", 0.0)
        )
        print(f"[Memory] Updated memory for {affected_service}")

    # Retrieve memory for context
    service_hint = affected_service or _extract_service_hint(
        state.get("incident_description", "")
    )

    memory = await get_service_memory(service_hint)

    # Convert memory into evidence
    evidence_items = []
    if memory["has_memory"]:
        evidence_items.append(f"[MEMORY] {memory['service']} had {memory['total_incidents']} previous incidents")

        if memory["common_causes"]:
            evidence_items.append(f"[MEMORY] Known causes: {', '.join(memory['common_causes'][:3])}")

        for runbook in memory["runbooks"][:2]:
            evidence_items.append(
                f"Proven runbook (used {runbook['times_used']}x, "
                f"confidence {runbook['confidence']}): "
                f"{runbook['trigger']} → {runbook['steps']}"
            )

    return {
        "evidence": evidence_items,
        "completed_tools": ["memory"]
    }

def _extract_service_hint(description: str) -> str:
    """
    Extracts likely service name from incident description.
    Simple keyword matching — good enough for now.
    """
    keywords = ["payment", "auth", "api", "database", "frontend",
                "notification", "order", "user", "search"]
    description_lower = description.lower()

    for keyword in keywords:
        if keyword in description_lower:
            return keyword

    return "unknown"

