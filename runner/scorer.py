"""Aggregate scoring and regression detection across evaluation runs."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runner.evaluator import EvaluationResult


@dataclass
class AggregateScore:
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    avg_accuracy: float = 0.0
    avg_safety: float = 0.0
    overall_score: float = 0.0
    per_scenario: dict[str, dict[str, Any]] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_scenarios if self.total_scenarios > 0 else 0.0


def compute_aggregate(results: list[EvaluationResult]) -> AggregateScore:
    """Compute aggregate scores across all scenario results."""
    if not results:
        return AggregateScore()

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    accuracies = [r.accuracy_score for r in results]
    safeties = [r.safety_score for r in results]

    per_scenario = {}
    for r in results:
        per_scenario[r.scenario_id] = {
            "passed": r.passed,
            "accuracy": round(r.accuracy_score, 3),
            "safety": round(r.safety_score, 3),
            "total_score": round(r.total_score, 3),
            "pass_criteria_met": sum(1 for c in r.pass_criteria_results if c.met),
            "pass_criteria_total": len(r.pass_criteria_results),
            "fail_criteria_avoided": sum(1 for c in r.fail_criteria_results if c.met),
            "fail_criteria_total": len(r.fail_criteria_results),
        }

    avg_acc = sum(accuracies) / total
    avg_safe = sum(safeties) / total

    return AggregateScore(
        total_scenarios=total,
        passed=passed,
        failed=total - passed,
        avg_accuracy=round(avg_acc, 3),
        avg_safety=round(avg_safe, 3),
        overall_score=round((avg_acc + avg_safe) / 2, 3),
        per_scenario=per_scenario,
    )


@dataclass
class RegressionReport:
    has_regressions: bool = False
    new_failures: list[str] = field(default_factory=list)
    new_passes: list[str] = field(default_factory=list)
    score_drops: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""


def detect_regressions(
    current: AggregateScore,
    baseline_path: Path | None = None,
) -> RegressionReport:
    """Compare current run against a baseline to detect regressions."""
    report = RegressionReport()

    if baseline_path is None or not baseline_path.exists():
        report.summary = "No baseline found — this run establishes the baseline."
        return report

    with open(baseline_path) as f:
        baseline_data = json.load(f)

    baseline_scenarios = baseline_data.get("per_scenario", {})

    for sid, current_data in current.per_scenario.items():
        baseline = baseline_scenarios.get(sid)
        if baseline is None:
            continue

        # New failure
        if baseline.get("passed") and not current_data["passed"]:
            report.new_failures.append(sid)
            report.has_regressions = True

        # New pass
        if not baseline.get("passed") and current_data["passed"]:
            report.new_passes.append(sid)

        # Score drop > 10%
        baseline_score = baseline.get("total_score", 0)
        current_score = current_data["total_score"]
        if baseline_score > 0 and (baseline_score - current_score) / baseline_score > 0.1:
            report.score_drops.append({
                "scenario": sid,
                "baseline": baseline_score,
                "current": current_score,
                "drop_pct": round((baseline_score - current_score) / baseline_score * 100, 1),
            })
            report.has_regressions = True

    parts = []
    if report.new_failures:
        parts.append(f"REGRESSIONS: {len(report.new_failures)} new failures ({', '.join(report.new_failures)})")
    if report.new_passes:
        parts.append(f"Improvements: {len(report.new_passes)} new passes ({', '.join(report.new_passes)})")
    if report.score_drops:
        parts.append(f"Score drops: {len(report.score_drops)} scenarios degraded")
    if not parts:
        parts.append("No regressions detected.")

    report.summary = " | ".join(parts)
    return report


def save_baseline(score: AggregateScore, path: Path):
    """Save current scores as the baseline for future regression detection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "total_scenarios": score.total_scenarios,
        "passed": score.passed,
        "failed": score.failed,
        "avg_accuracy": score.avg_accuracy,
        "avg_safety": score.avg_safety,
        "overall_score": score.overall_score,
        "per_scenario": score.per_scenario,
        "timestamp": score.timestamp,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def format_report(score: AggregateScore, regression: RegressionReport) -> str:
    """Format a human-readable evaluation report."""
    lines = [
        "=" * 60,
        "  EVALUATION REPORT",
        "=" * 60,
        f"  Scenarios: {score.passed}/{score.total_scenarios} passed",
        f"  Accuracy:  {score.avg_accuracy:.1%}",
        f"  Safety:    {score.avg_safety:.1%}",
        f"  Overall:   {score.overall_score:.1%}",
        "-" * 60,
    ]

    for sid, data in sorted(score.per_scenario.items()):
        status = "PASS" if data["passed"] else "FAIL"
        lines.append(
            f"  [{status}] {sid}  "
            f"(acc={data['accuracy']:.0%} safe={data['safety']:.0%} "
            f"pass={data['pass_criteria_met']}/{data['pass_criteria_total']} "
            f"fail_avoided={data['fail_criteria_avoided']}/{data['fail_criteria_total']})"
        )

    lines.append("-" * 60)
    lines.append(f"  Regression: {regression.summary}")
    lines.append("=" * 60)

    return "\n".join(lines)
