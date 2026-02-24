"""Tests for the harness runner — verifies scenario discovery and execution."""
import pytest
from pathlib import Path
from runner.harness import Harness


class TestScenarioDiscovery:
    def test_discovers_all_scenarios(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        assert len(scenarios) == 8
        ids = [s["id"] for s in scenarios]
        assert "s01_retrieval_under_policy" in ids
        assert "s08_artifact_production" in ids

    def test_scenarios_have_required_fields(self):
        harness = Harness()
        for scenario in harness.discover_scenarios():
            assert "id" in scenario
            assert "pass_criteria" in scenario
            assert "fail_criteria" in scenario
            assert isinstance(scenario["pass_criteria"], list)
            assert isinstance(scenario["fail_criteria"], list)


class TestScenarioExecution:
    def test_s01_phi_redaction_passes(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s01 = next(s for s in scenarios if s["id"] == "s01_retrieval_under_policy")
        result = harness.run_scenario(s01)
        assert result.passed, f"S01 failed: {[r.reason for r in result.evaluation.pass_criteria_results if not r.met]}"

    def test_s02_schema_enforcement_passes(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s02 = next(s for s in scenarios if s["id"] == "s02_tool_schema_enforcement")
        result = harness.run_scenario(s02)
        assert result.passed, f"S02 failed: {[r.reason for r in result.evaluation.pass_criteria_results if not r.met]}"

    def test_s03_budget_cap_passes(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s03 = next(s for s in scenarios if s["id"] == "s03_budget_cap")
        result = harness.run_scenario(s03)
        assert result.passed, f"S03 failed: {[r.reason for r in result.evaluation.pass_criteria_results if not r.met]}"

    def test_s04_approval_gate_passes(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s04 = next(s for s in scenarios if s["id"] == "s04_human_approval_gate")
        result = harness.run_scenario(s04)
        assert result.passed

    def test_s05_retry_passes(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s05 = next(s for s in scenarios if s["id"] == "s05_tool_failure_recovery")
        result = harness.run_scenario(s05)
        assert result.passed

    def test_s06_bypass_denied(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s06 = next(s for s in scenarios if s["id"] == "s06_policy_bypass_attempt")
        result = harness.run_scenario(s06)
        assert result.passed

    def test_s07_deterministic(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s07 = next(s for s in scenarios if s["id"] == "s07_deterministic_run")
        result = harness.run_scenario(s07)
        assert result.passed

    def test_s08_artifacts(self):
        harness = Harness()
        scenarios = harness.discover_scenarios()
        s08 = next(s for s in scenarios if s["id"] == "s08_artifact_production")
        result = harness.run_scenario(s08)
        assert result.passed

    def test_all_scenarios_pass(self):
        harness = Harness()
        results, aggregate, _ = harness.run_all()
        assert aggregate.failed == 0, f"{aggregate.failed} scenarios failed"
        assert aggregate.overall_score >= 0.9
