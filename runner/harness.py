"""Main harness runner — discovers scenarios, executes them, and evaluates results."""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adapters.mock.adapter import MockAdapter
from runner.evaluator import evaluate_scenario, EvaluationResult
from runner.scorer import (
    compute_aggregate,
    detect_regressions,
    save_baseline,
    format_report,
    AggregateScore,
    RegressionReport,
)

BASELINE_PATH = Path("bundles/outputs/baseline.json")


@dataclass
class ScenarioResult:
    scenario_id: str
    evaluation: EvaluationResult
    duration_ms: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.evaluation.passed


class Harness:
    def __init__(self, scenarios_dir: str = "scenarios"):
        self.scenarios_dir = Path(scenarios_dir)

    def discover_scenarios(self) -> list[dict]:
        scenarios = []
        for f in sorted(self.scenarios_dir.glob("*/scenario.json")):
            with open(f) as fh:
                scenarios.append(json.load(fh))
        return scenarios

    def _build_adapter_config(self, scenario: dict) -> dict:
        """Build adapter config tuned to the scenario."""
        config = scenario.get("config", {})
        adapter_config = {}
        if "budget_limit" in config:
            adapter_config["budget_limit"] = config["budget_limit"]
        if "cost_per_call" in config:
            adapter_config["cost_per_call"] = config["cost_per_call"]
        return adapter_config

    def run_scenario(self, scenario: dict) -> ScenarioResult:
        start = time.monotonic()
        config = scenario.get("config", {})
        adapter = MockAdapter(self._build_adapter_config(scenario))

        # Execute with scenario-specific context
        context = dict(config)
        context["scenario_id"] = scenario["id"]
        response = adapter.execute("query", context)

        # Special handling for deterministic check (S07)
        if "Two runs produce identical trace hashes" in scenario.get("pass_criteria", []):
            first_hash = adapter.state.trace_hash
            adapter2 = MockAdapter(self._build_adapter_config(scenario))
            context2 = dict(config)
            context2["scenario_id"] = scenario["id"]
            adapter2.execute("query", context2)
            second_hash = adapter2.state.trace_hash
            context["_deterministic_verified"] = first_hash == second_hash
            context["_hash_mismatch"] = first_hash != second_hash

        duration = (time.monotonic() - start) * 1000

        evaluation = evaluate_scenario(
            scenario_id=scenario["id"],
            state=adapter.state,
            pass_criteria=scenario.get("pass_criteria", []),
            fail_criteria=scenario.get("fail_criteria", []),
            context=context,
        )

        return ScenarioResult(
            scenario_id=scenario["id"],
            evaluation=evaluation,
            duration_ms=duration,
            metrics={
                "latency_ms": duration,
                "tokens": response.tokens_used,
                "policy_receipts": response.metadata.get("policy_receipts", 0),
                "accuracy": evaluation.accuracy_score,
                "safety": evaluation.safety_score,
            },
        )

    def run_all(self) -> tuple[list[ScenarioResult], AggregateScore, RegressionReport]:
        results = []
        print("Running scenarios...\n")

        for scenario in self.discover_scenarios():
            result = self.run_scenario(scenario)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            acc = result.evaluation.accuracy_score
            safe = result.evaluation.safety_score
            print(f"  [{status}] {result.scenario_id} (acc={acc:.0%} safe={safe:.0%} {result.duration_ms:.1f}ms)")

        evaluations = [r.evaluation for r in results]
        aggregate = compute_aggregate(evaluations)
        regression = detect_regressions(aggregate, BASELINE_PATH)

        # Save as new baseline
        save_baseline(aggregate, BASELINE_PATH)

        print()
        print(format_report(aggregate, regression))

        return results, aggregate, regression


if __name__ == "__main__":
    harness = Harness()
    results, aggregate, regression = harness.run_all()
    exit_code = 0 if aggregate.failed == 0 else 1
    exit(exit_code)
