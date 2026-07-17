from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.evaluation.evaluator import (
    evaluate_investigation,
    _evidence_grounding_score,
    _llm_judge_score,
)
from backend.evaluation.test_cases import TEST_CASES
from backend.agents.graph import investigation_graph
from backend.core.auth import get_current_user
from fastapi import Depends
import os
import json
import pathlib
from datetime import datetime

# Path to persist the last evaluation run result
EVAL_CACHE_FILE = pathlib.Path(__file__).parent.parent / "evaluation" / "last_results.json"

router = APIRouter(prefix="/api", tags=["evaluation"])


class ReportEvalRequest(BaseModel):
    log_content: str
    final_report: dict  # the actual report dict from the investigation result


@router.post("/evaluation/report")
async def evaluate_report(
    request: ReportEvalRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Evaluates a real investigation report using the two ground-truth-free
    dimensions: evidence grounding and LLM-as-judge.
    Called by the dashboard "Evaluate Report" button after an investigation finishes.
    """
    report = request.final_report
    log = request.log_content

    evidence_score = _evidence_grounding_score(
        evidence_items=report.get("evidence", []),
        log_content=log
    )

    llm_score = await _llm_judge_score(
        log_content=log,
        actual_report=report
    )

    overall = round((evidence_score + llm_score) / 2, 3)

    return {
        "evidence_grounding": evidence_score,
        "llm_judge": llm_score,
        "overall": overall,
        "note": "Scored using evidence grounding + LLM-as-judge (no ground truth required)"
    }


@router.post("/evaluation/run")
async def run_evaluation(current_user: dict = Depends(get_current_user)):
    """
    Runs all test cases through the investigation pipeline
    and scores the results.
    """
    os.environ["EVAL_MODE"] = "true"
    results = []
    total_score = 0.0

    for test_case in TEST_CASES:
        print(f"\n[Eval] Running test case: {test_case['name']}")

        # Run investigation
        initial_state = {
            "incident_description": test_case["name"],
            "log_content": test_case["log_content"],
            "evidence": [],
            "log_findings": {},
            "similar_incidents": [],
            "github_commits": [],
            "failed_tools": [],
            "completed_tools": [],
            "final_report": {},
            "investigation_id": test_case["id"]
        }

        final_state = await investigation_graph.ainvoke(initial_state)
        actual_report = final_state["final_report"]

        # Evaluate
        eval_result = await evaluate_investigation(
            test_case=test_case,
            actual_report=actual_report,
            log_content=test_case["log_content"]
        )

        results.append({
            "test_case": test_case["name"],
            "scores": eval_result["scores"],
            "overall_score": eval_result["overall_score"],
            "passed": eval_result["passed"],
            "actual_severity": actual_report.get("severity"),
            "actual_service": actual_report.get("affected_service"),
            "actual_cause": actual_report.get("probable_cause")
        })

        total_score += eval_result["overall_score"]
        status = "✅ PASS" if eval_result["passed"] else "❌ FAIL"
        print(f"[Eval] {test_case['name']}: {eval_result['overall_score']} {status}")

    avg_score = round(total_score / len(TEST_CASES), 3)
    os.environ["EVAL_MODE"] = "false"

    passed = sum(1 for r in results if r["passed"])

    # Compute per-dimension averages across all test cases
    dimension_keys = ["rule_based", "evidence_grounding", "semantic_similarity", "llm_judge"]
    dimension_avgs = {
        key: round(sum(r["scores"][key] for r in results) / len(results), 3)
        for key in dimension_keys
    }

    payload = {
        "total_test_cases": len(TEST_CASES),
        "passed": passed,
        "failed": len(TEST_CASES) - passed,
        "average_score": avg_score,
        "dimension_averages": dimension_avgs,
        "results": results,
        "evaluated_at": datetime.utcnow().isoformat()
    }

    # Persist to cache so /latest can serve it without re-running
    try:
        EVAL_CACHE_FILE.write_text(json.dumps(payload, indent=2))
    except Exception as e:
        print(f"[Eval] Failed to write cache: {e}")

    return payload


@router.get("/evaluation/latest")
async def get_latest_evaluation(current_user: dict = Depends(get_current_user)):
    """
    Returns the most recently cached evaluation result.
    If no evaluation has been run yet, returns None.
    """
    if not EVAL_CACHE_FILE.exists():
        return {"available": False}

    try:
        data = json.loads(EVAL_CACHE_FILE.read_text())
        data["available"] = True
        return data
    except Exception:
        return {"available": False}


@router.get("/evaluation/test-cases")
async def list_test_cases():
    """Returns all available test cases."""
    return {
        "total": len(TEST_CASES),
        "test_cases": [
            {"id": tc["id"], "name": tc["name"]}
            for tc in TEST_CASES
        ]
    }