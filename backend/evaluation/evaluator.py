import json
import httpx
from datetime import datetime
from backend.core.config import settings
from backend.services.vector_service import generate_embedding

async def evaluate_investigation(
    test_case: dict,
    actual_report: dict,
    log_content: str
) -> dict:
    """
    Scores an investigation report against ground truth.
    Returns scores across four dimensions.
    """

    scores = {}

    # ── 1. Rule-based checks ──────────────────────────────
    rule_score = _rule_based_score(test_case["expected"], actual_report)
    scores["rule_based"] = rule_score

    # ── 2. Evidence grounding ─────────────────────────────
    grounding_score = _evidence_grounding_score(
        actual_report.get("evidence", []),
        log_content
    )
    scores["evidence_grounding"] = grounding_score

    # ── 3. Semantic similarity ────────────────────────────
    similarity_score = await _semantic_similarity_score(
        test_case["expected"],
        actual_report
    )
    scores["semantic_similarity"] = similarity_score

    # ── 4. LLM-as-judge ───────────────────────────────────
    llm_score = await _llm_judge_score(
        log_content,
        actual_report
    )
    scores["llm_judge"] = llm_score

    # ── Overall score ─────────────────────────────────────
    overall = round(
        scores["rule_based"] * 0.25 +
        scores["evidence_grounding"] * 0.25 +
        scores["semantic_similarity"] * 0.25 +
        scores["llm_judge"] * 0.25,
        3
    )

    return {
        "test_case_id": test_case["id"],
        "test_case_name": test_case["name"],
        "scores": scores,
        "overall_score": overall,
        "passed": overall >= 0.7,
        "evaluated_at": datetime.utcnow().isoformat()
    }

def _rule_based_score(expected: dict, actual: dict) -> float:
    """
    Checks structural correctness and field accuracy.
    """
    score = 0.0
    checks = 0

    # Severity match
    checks += 1
    if actual.get("severity", "").lower() == expected.get("severity", "").lower():
        score += 1.0

    # Service match
    checks += 1
    expected_service = expected.get("affected_service", "").lower()
    actual_service = actual.get("affected_service", "").lower()
    if expected_service in actual_service or actual_service in expected_service:
        score += 1.0

    # Probable cause contains expected keywords
    checks += 1
    cause = actual.get("probable_cause", "").lower()
    cause_keywords = expected.get("probable_cause_keywords", [])
    if cause_keywords:
        matches = sum(1 for kw in cause_keywords if kw.lower() in cause)
        score += matches / len(cause_keywords)

    # Actions contain expected keywords
    checks += 1
    actions = " ".join(actual.get("immediate_actions", [])).lower()
    action_keywords = expected.get("expected_actions_keywords", [])
    if action_keywords:
        matches = sum(1 for kw in action_keywords if kw.lower() in actions)
        score += matches / len(action_keywords)

    # Confidence is reasonable
    checks += 1
    confidence = actual.get("confidence", 0)
    if 0.5 <= confidence <= 1.0:
        score += 1.0

    return round(score / checks, 3)

def _evidence_grounding_score(
    evidence_items: list,
    log_content: str
) -> float:
    """
    Checks if evidence items are grounded in actual log content.
    Penalizes hallucinated evidence not found in the log.
    """
    if not evidence_items:
        return 0.0

    log_lower = log_content.lower()
    grounded = 0

    for item in evidence_items:
        item_lower = item.lower()

        # Extract key phrases from evidence item
        words = [w for w in item_lower.split() if len(w) > 4]
        if not words:
            continue

        # Check if meaningful words from evidence appear in log
        matches = sum(1 for w in words if w in log_lower)
        if matches / len(words) >= 0.3:
            grounded += 1

    return round(grounded / len(evidence_items), 3)

async def _semantic_similarity_score(
    expected: dict,
    actual: dict
) -> float:
    """
    Uses embeddings to measure semantic similarity between
    expected and actual probable cause.
    """
    try:
        expected_text = " ".join(expected.get("probable_cause_keywords", []))
        actual_cause = actual.get("probable_cause", "")

        if not expected_text or not actual_cause:
            return 0.5

        expected_embedding = await generate_embedding(expected_text)
        actual_embedding = await generate_embedding(actual_cause)

        # Cosine similarity
        dot_product = sum(
            a * b for a, b in zip(expected_embedding, actual_embedding)
        )
        magnitude_a = sum(a ** 2 for a in expected_embedding) ** 0.5
        magnitude_b = sum(b ** 2 for b in actual_embedding) ** 0.5

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        similarity = dot_product / (magnitude_a * magnitude_b)
        return round(max(0.0, similarity), 3)

    except Exception as e:
        print(f"[Eval] Semantic similarity failed: {e}")
        return 0.5

async def _llm_judge_score(
    log_content: str,
    actual_report: dict
) -> float:
    """
    Uses LLM to judge investigation quality.
    Scores on accuracy, completeness, and actionability.
    """
    try:
        prompt = f"""You are an expert evaluator of incident investigation reports.
Score this investigation report from 0.0 to 1.0.
Respond with ONLY a JSON object, no markdown.

Scoring criteria:
- accuracy: does the probable cause match the log evidence?
- completeness: are all important issues identified?
- actionability: are the immediate actions specific and useful?

Required response format:
{{
    "accuracy": 0.0,
    "completeness": 0.0,
    "actionability": 0.0,
    "reasoning": "one sentence"
}}

Log content:
{log_content[:500]}

Investigation report:
- Severity: {actual_report.get('severity')}
- Affected service: {actual_report.get('affected_service')}
- Probable cause: {actual_report.get('probable_cause')}
- Evidence: {actual_report.get('evidence', [])[:3]}
- Actions: {actual_report.get('immediate_actions', [])[:3]}"""

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert evaluator. Respond only with valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "num_predict": 200,
                        "temperature": 0.1
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
            result = json.loads(raw[start:end])

            avg = (
                result.get("accuracy", 0) +
                result.get("completeness", 0) +
                result.get("actionability", 0)
            ) / 3

            print(f"[Eval] LLM judge: {result.get('reasoning', '')}")
            return round(avg, 3)

    except Exception as e:
        print(f"[Eval] LLM judge failed: {e}")
        return 0.5