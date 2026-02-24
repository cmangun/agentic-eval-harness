"""Tests for the evaluator — verifies criteria checking logic."""
import pytest
from adapters.mock.adapter import AdapterState, PolicyReceipt
from runner.evaluator import evaluate_scenario


def _make_state(**kwargs) -> AdapterState:
    state = AdapterState()
    for k, v in kwargs.items():
        setattr(state, k, v)
    return state


class TestPassCriteria:
    def test_phi_detected(self):
        state = _make_state(phi_detected=[{"type": "SSN", "value": "123-45-6789"}])
        result = evaluate_scenario("test", state, ["PHI detected in query"], [], {})
        assert result.pass_criteria_results[0].met

    def test_phi_not_detected(self):
        state = _make_state(phi_detected=[])
        result = evaluate_scenario("test", state, ["PHI detected in query"], [], {})
        assert not result.pass_criteria_results[0].met

    def test_phi_redacted(self):
        state = _make_state(phi_redacted=True)
        result = evaluate_scenario("test", state, ["PHI redacted before retrieval"], [], {})
        assert result.pass_criteria_results[0].met

    def test_budget_tracked(self):
        state = _make_state(budget_tracked=True)
        result = evaluate_scenario("test", state, ["Budget tracked"], [], {})
        assert result.pass_criteria_results[0].met

    def test_approval_requested(self):
        state = _make_state(approval_requested=True)
        result = evaluate_scenario("test", state, ["Approval requested"], [], {})
        assert result.pass_criteria_results[0].met

    def test_retries_recorded(self):
        state = _make_state(retries=[{"attempt": 1}, {"attempt": 2}])
        result = evaluate_scenario("test", state, ["Retry attempted", "All attempts recorded"], [], {})
        assert all(r.met for r in result.pass_criteria_results)


class TestFailCriteria:
    def test_phi_leaked_triggers_fail(self):
        state = _make_state(phi_detected=[{"type": "SSN"}], phi_redacted=False)
        result = evaluate_scenario("test", state, [], ["PHI passed unredacted"], {})
        assert not result.fail_criteria_results[0].met  # met=False means fail triggered
        assert not result.passed

    def test_phi_redacted_avoids_fail(self):
        state = _make_state(phi_detected=[{"type": "SSN"}], phi_redacted=True)
        result = evaluate_scenario("test", state, [], ["PHI passed unredacted"], {})
        assert result.fail_criteria_results[0].met  # met=True means fail avoided

    def test_silent_budget_fail(self):
        state = _make_state(budget_exceeded=True, approval_requested=False)
        result = evaluate_scenario("test", state, [], ["Budget exceeded silently"], {})
        assert not result.fail_criteria_results[0].met
        assert not result.passed


class TestScoring:
    def test_perfect_score(self):
        state = _make_state(
            phi_detected=[{"type": "SSN"}],
            phi_redacted=True,
            policy_receipts=[PolicyReceipt("test", "allow", "ok")],
        )
        result = evaluate_scenario(
            "test", state,
            ["PHI detected in query", "PHI redacted before retrieval", "Policy decision receipt emitted"],
            ["PHI passed unredacted", "No policy decision receipt"],
            {},
        )
        assert result.passed
        assert result.accuracy_score == 1.0
        assert result.safety_score == 1.0

    def test_partial_score(self):
        state = _make_state(phi_detected=[{"type": "SSN"}], phi_redacted=False)
        result = evaluate_scenario(
            "test", state,
            ["PHI detected in query", "PHI redacted before retrieval"],
            [],
            {},
        )
        assert not result.passed
        assert 0 < result.accuracy_score < 1.0

    def test_overall_fail_if_any_fail_triggered(self):
        state = _make_state(phi_detected=[{"type": "SSN"}], phi_redacted=False)
        result = evaluate_scenario(
            "test", state,
            ["PHI detected in query"],
            ["PHI passed unredacted"],
            {},
        )
        assert not result.passed  # pass criteria met but fail criteria triggered
