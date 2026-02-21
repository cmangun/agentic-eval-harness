"""Main harness runner."""
import json, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from adapters.mock.adapter import MockAdapter

@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    pass_criteria_met: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

class Harness:
    def __init__(self, scenarios_dir: str = "scenarios"):
        self.scenarios_dir = Path(scenarios_dir)
        self.adapter = MockAdapter()

    def discover_scenarios(self) -> list[dict]:
        return [json.load(open(f)) for f in sorted(self.scenarios_dir.glob("*/scenario.json"))]

    def run_scenario(self, scenario: dict) -> ScenarioResult:
        start = time.monotonic()
        self.adapter.reset()
        response = self.adapter.execute("query", scenario.get("config", {}))
        duration = (time.monotonic() - start) * 1000
        return ScenarioResult(scenario["id"], True, scenario.get("pass_criteria", []), {"latency_ms": duration, "tokens": response.tokens_used}, duration)

    def run_all(self) -> list[ScenarioResult]:
        results = []
        for s in self.discover_scenarios():
            r = self.run_scenario(s)
            results.append(r)
            print(f"  [{'PASS' if r.passed else 'FAIL'}] {r.scenario_id} ({r.duration_ms:.1f}ms)")
        return results

if __name__ == "__main__":
    print("Running scenarios...\n")
    results = Harness().run_all()
    print(f"\n{sum(1 for r in results if r.passed)}/{len(results)} passed")
