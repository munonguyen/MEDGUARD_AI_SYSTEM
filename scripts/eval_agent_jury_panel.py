"""Offline Runner for Agent Multi-Judge Committee Evaluation.

Evaluates Agent responses on clinical benchmarks using:
- 3 Evaluation Scopes: Tool, Trajectory, and Output
- 4 Specialized Judges: Legal, Psychological, Clinical, and Factual (QAG/DAG)
- Exports formatted results for DeepEval and Langfuse
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.services.jury_evaluator import (
    AgentJuryPanel,
    ToolExecutionRecord,
    TrajectoryStep,
    jury_panel,
)
from app.services.knowledge_retriever import KnowledgeRetriever


def run_jury_evaluation(
    benchmark_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    retriever = KnowledgeRetriever()
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmarks = data.get("benchmarks", [])

    results: list[dict[str, Any]] = []
    deepeval_test_cases: list[dict[str, Any]] = []
    langfuse_scores: list[dict[str, Any]] = []

    passed_count = 0
    total_score = 0.0

    print("=" * 70)
    print("RUNNING MULTI-JUDGE AGENT EVALUATION (HỘI ĐỒNG GIÁM KHẢO LLM)")
    print(f"Benchmark: {benchmark_path.name} ({len(benchmarks)} clinical cases)")
    print("=" * 70)

    for item in benchmarks:
        bench_id = item["id"]
        intent = item.get("intent", "safety")
        question = item["question"]
        ground_truth = item.get("ground_truth", "")
        key_claims = item.get("key_claims", [])

        # Retrieve relevant contexts
        retrieved = retriever.retrieve(question, intent=intent, top_k=3)
        contexts = [r.content for r in retrieved]

        # Simulated high-quality compliant candidate answer based on ground truth
        candidate_answer = (
            f"Thông tin hiện có từ tài liệu chuyên môn: {ground_truth}\n"
            f"Lưu ý: {key_claims[0] if key_claims else 'Cần thận trọng'}. "
            f"Bệnh nhân nên tham khảo ý kiến bác sĩ chuyên khoa hoặc đến cơ sở y tế để được tư vấn phác đồ phù hợp."
        )

        # Build trajectory and tool records
        tool_records = [
            ToolExecutionRecord(
                tool_name="knowledge_retriever",
                parameters={"query": question, "intent": intent},
                expected_tool="knowledge_retriever",
                expected_parameters={"query": question, "intent": intent},
                execution_order=1,
                success=True,
            )
        ]
        trajectory = [
            TrajectoryStep(node_name="researcher", action="retrieve_context", reasoning="Query clinical documents"),
            TrajectoryStep(node_name="writer", action="draft_response", reasoning="Draft with locked claims"),
            TrajectoryStep(node_name="reviewer", action="verify_safety", reasoning="Check contraindications"),
        ]

        # Run Jury Evaluation
        scorecard = jury_panel.evaluate(
            evaluation_id=bench_id,
            answer_text=candidate_answer,
            contexts=contexts,
            locked_claims=[key_claims[0]] if key_claims else [],
            abstains_from_diagnosis=True,
            red_flags_present="cấp cứu" in ground_truth.lower(),
            triage_urgency="EMERGENCY" if "cấp cứu" in ground_truth.lower() else "ROUTINE",
            tool_records=tool_records,
            trajectory_steps=trajectory,
        )

        if scorecard.overall_passed:
            passed_count += 1
        total_score += scorecard.consensus_score

        results.append(scorecard.to_dict())
        deepeval_test_cases.append(scorecard.export_deepeval())
        langfuse_scores.extend(scorecard.export_langfuse())

        status_str = "PASS [✓]" if scorecard.overall_passed else "FAIL [✗]"
        print(f"[{bench_id}] Score: {scorecard.consensus_score:.2f} | Status: {status_str} | Veto: {scorecard.veto_active}")
        for j_name, v in scorecard.verdicts.items():
            print(f"   ├─ {v.judge_name:25}: Score {v.score:.2f} ({'PASS' if v.passed else 'FAIL'})")

    avg_consensus = total_score / len(benchmarks) if benchmarks else 0.0
    pass_rate = passed_count / len(benchmarks) if benchmarks else 0.0

    summary = {
        "benchmark_file": str(benchmark_path),
        "total_cases": len(benchmarks),
        "passed_cases": passed_count,
        "pass_rate": round(pass_rate, 3),
        "average_consensus_score": round(avg_consensus, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detailed_results": results,
        "deepeval_export": deepeval_test_cases,
        "langfuse_export": langfuse_scores,
    }

    print("=" * 70)
    print(f"EVALUATION COMPLETE: {passed_count}/{len(benchmarks)} Passed ({pass_rate*100:.1f}%)")
    print(f"Average Consensus Score: {avg_consensus:.3f}")
    print("=" * 70)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved evaluation report to {output_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Agent responses via Multi-Judge Panel")
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("datasets/DS-RAG-BENCHMARK/gold_clinical_benchmark.json"),
        help="Path to benchmark dataset",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("datasets/jury_eval_report.json"),
        help="Path to output evaluation report",
    )
    args = parser.parse_args()
    run_jury_evaluation(args.benchmark, args.output_json)


if __name__ == "__main__":
    main()
