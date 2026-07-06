from fastapi import APIRouter
from backend.evaluation.evaluator import evaluate_investigation
from backend.evaluation.test_cases import TEST_CASES
from backend.agents.graph import investigation_graph
import os

router = APIRouter(prefix="/api", tags=["evaluation"])

@router.post("/evaluation/run")
async def run_evaluation():
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
            "db_anomalies": [],
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
    
    return {
        "total_test_cases": len(TEST_CASES),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "average_score": avg_score,
        "results": results
    }

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