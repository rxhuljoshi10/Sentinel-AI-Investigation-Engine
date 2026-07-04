import httpx
import json
from backend.core.config import settings
from backend.agents.state import InvestigationState
from backend.services.vector_service import search_similar_incidents
from backend.models.schemas import InvestigationReport
from backend.services.function_calling_service import run_function_calling
from backend.tools.database_tool import save_incident_to_db

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
            for commit in commits[:3]:
                evidence_items.append(
                    f"GitHub commit: '{commit['message']}' "
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
            f"Log analysis - Timeline: {findings.get('timeline', 'unknown')}",
            f"Log analysis - Affected: {', '.join(findings.get('affected_components', []))}",
        ]
        for pattern in findings.get("error_patterns", [])[:3]:
            evidence_items.append(f"Log pattern: {pattern}")

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
                f"Similar past incident (score: {incident.similarity_score}): "
                f"{incident.probable_cause} → resolved by: "
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

# ─── GitHub Searcher Node ────────────────────────────────────────────────────

# async def github_searcher_node(state: InvestigationState) -> dict:
#     """
#     Simulates checking GitHub for recent commits near the incident time.
#     In v0.5 this will use real GitHub API via MCP.
#     """
#     print("[GitHub Searcher] Checking recent commits...")

#     # Simulated for now - real GitHub integration comes in v0.5
#     log_findings = state.get("log_findings", {})
#     affected = log_findings.get("affected_components", ["unknown-service"])

#     simulated_commits = [
#         {
#             "sha": "a3f9c21",
#             "message": f"Update connection pool config in {affected[0] if affected else 'service'}",
#             "author": "dev-team",
#             "time": "2 hours before incident"
#         }
#     ]

#     evidence_items = []
#     for commit in simulated_commits:
#         evidence_items.append(
#             f"Recent commit ({commit['time']}): '{commit['message']}' "
#             f"by {commit['author']} [{commit['sha']}]"
#         )

#     print(f"[GitHub Searcher] Found {len(simulated_commits)} recent commits")

#     return {
#         "github_commits": simulated_commits,
#         "evidence": evidence_items,
#         "completed_tools": ["github_searcher"]
#     }

# ─── Reasoner Node ───────────────────────────────────────────────────────────

async def reasoner_node(state: InvestigationState) -> dict:
    print(f"[Reasoner] Synthesizing {len(state.get('evidence', []))} evidence items...")

    evidence_block = "\n".join([
        f"- {item}" for item in state.get("evidence", [])
    ])

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
                "content": f"""Investigate this incident and reply with ONLY a JSON object.

Required keys:
- severity: "critical", "high", "medium", or "low"
- affected_service: service name (string)
- probable_cause: one sentence root cause (string)
- evidence: list of 3 key evidence items (strings)
- immediate_actions: list of 3 fix steps (strings)
- confidence: number 0.0 to 1.0
- investigation_summary: two sentence summary (string)

Incident: {state['incident_description']}
Tools completed: {', '.join(completed)}
Tools failed: {', '.join(failed) if failed else 'none'}

Evidence:
{evidence_block[:1500]}"""
            }
        ])

        print("[Reasoner] Report generated successfully")
        return {"final_report": report}

    except Exception as e:
        print(f"[Reasoner] Failed after retries: {e}")
        return {
            "final_report": {
                "severity": "unknown",
                "affected_service": "unknown",
                "probable_cause": f"Reasoner failed: {str(e)}",
                "evidence": state.get("evidence", [])[:3],
                "immediate_actions": ["Manual investigation required"],
                "confidence": 0.0,
                "investigation_summary": "Automated investigation failed."
            }
        }