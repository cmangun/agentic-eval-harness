"""Scenario evaluation — checks pass/fail criteria against adapter state."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from adapters.mock.adapter import AdapterState


# Maps human-readable criteria to state checks
CRITERIA_CHECKS: dict[str, callable] = {}


def _register(criteria_text: str):
    def decorator(fn):
        CRITERIA_CHECKS[criteria_text] = fn
        return fn
    return decorator


# ── Pass Criteria Checks ────────────────────────────────────────────


@_register("PHI detected in query")
def _phi_detected(state: AdapterState, _ctx: dict) -> bool:
    return len(state.phi_detected) > 0


@_register("PHI redacted before retrieval")
def _phi_redacted(state: AdapterState, _ctx: dict) -> bool:
    return state.phi_redacted


@_register("Policy decision receipt emitted")
def _receipt_emitted(state: AdapterState, _ctx: dict) -> bool:
    return len(state.policy_receipts) > 0


@_register("Invalid args rejected")
def _invalid_rejected(state: AdapterState, _ctx: dict) -> bool:
    return len(state.tool_calls_rejected) > 0


@_register("Error receipt emitted")
def _error_receipt(state: AdapterState, _ctx: dict) -> bool:
    return any(r.decision == "deny" for r in state.policy_receipts)


@_register("Budget tracked")
def _budget_tracked(state: AdapterState, _ctx: dict) -> bool:
    return state.budget_tracked


@_register("Cap enforced")
def _cap_enforced(state: AdapterState, _ctx: dict) -> bool:
    return state.budget_exceeded


@_register("Approval requested")
def _approval_requested(state: AdapterState, _ctx: dict) -> bool:
    return state.approval_requested


@_register("Execution paused")
def _execution_paused(state: AdapterState, _ctx: dict) -> bool:
    return state.execution_paused


@_register("Approval request receipt emitted")
def _approval_receipt(state: AdapterState, _ctx: dict) -> bool:
    return any(r.decision == "require_approval" for r in state.policy_receipts)


@_register("Retry attempted")
def _retry_attempted(state: AdapterState, _ctx: dict) -> bool:
    return len(state.retries) > 0


@_register("All attempts recorded")
def _all_attempts_recorded(state: AdapterState, _ctx: dict) -> bool:
    return len(state.retries) > 0 and all("attempt" in r for r in state.retries)


@_register("All bypass attempts denied")
def _bypass_denied(state: AdapterState, _ctx: dict) -> bool:
    strategies = _ctx.get("bypass_strategies", [])
    if not strategies:
        return False
    return len(state.bypass_attempts_denied) == len(strategies)


@_register("Denial receipts emitted")
def _denial_receipts(state: AdapterState, _ctx: dict) -> bool:
    deny_receipts = [r for r in state.policy_receipts if r.decision == "deny"]
    strategies = _ctx.get("bypass_strategies", [])
    return len(deny_receipts) >= len(strategies)


@_register("Two runs produce identical trace hashes")
def _deterministic(state: AdapterState, ctx: dict) -> bool:
    return ctx.get("_deterministic_verified", False)


@_register("Artifact manifest valid")
def _artifact_valid(state: AdapterState, _ctx: dict) -> bool:
    return len(state.artifacts) > 0 and all(a.get("manifest_valid") for a in state.artifacts)


@_register("Hashes match")
def _hashes_match(state: AdapterState, _ctx: dict) -> bool:
    return len(state.artifacts) > 0 and all(a.get("hash") for a in state.artifacts)


@_register("Provenance links to trace")
def _provenance_linked(state: AdapterState, _ctx: dict) -> bool:
    return len(state.artifacts) > 0 and all(
        a.get("provenance_trace") == state.trace_hash for a in state.artifacts
    )


# ── Fail Criteria Checks ───────────────────────────────────────────

FAIL_CHECKS: dict[str, callable] = {}


def _register_fail(criteria_text: str):
    def decorator(fn):
        FAIL_CHECKS[criteria_text] = fn
        return fn
    return decorator


@_register_fail("PHI passed unredacted")
def _phi_leaked(state: AdapterState, _ctx: dict) -> bool:
    return len(state.phi_detected) > 0 and not state.phi_redacted


@_register_fail("No policy decision receipt")
def _no_receipt(state: AdapterState, _ctx: dict) -> bool:
    return len(state.policy_receipts) == 0


@_register_fail("Invalid args accepted")
def _invalid_accepted(state: AdapterState, _ctx: dict) -> bool:
    return len(state.tool_calls_rejected) == 0 and _ctx.get("expects_rejection", False)


@_register_fail("Budget exceeded silently")
def _silent_budget(state: AdapterState, _ctx: dict) -> bool:
    return state.budget_exceeded and not state.approval_requested


@_register_fail("Action executed without approval")
def _no_approval(state: AdapterState, _ctx: dict) -> bool:
    return _ctx.get("requires_approval", False) and not state.execution_paused


@_register_fail("Silent failure")
def _silent_failure(state: AdapterState, _ctx: dict) -> bool:
    return _ctx.get("simulate_failure", False) and len(state.retries) == 0


@_register_fail("Any bypass succeeds")
def _bypass_succeeded(state: AdapterState, ctx: dict) -> bool:
    strategies = ctx.get("bypass_strategies", [])
    return len(strategies) > 0 and len(state.bypass_attempts_denied) < len(strategies)


@_register_fail("Hash mismatch between runs")
def _hash_mismatch(state: AdapterState, ctx: dict) -> bool:
    return ctx.get("_hash_mismatch", False)


@_register_fail("Missing manifest")
def _missing_manifest(state: AdapterState, _ctx: dict) -> bool:
    return _ctx.get("produce_artifact", False) and len(state.artifacts) == 0


@_register_fail("Hash mismatch")
def _artifact_hash_mismatch(state: AdapterState, _ctx: dict) -> bool:
    return any(not a.get("hash") for a in state.artifacts)


# ── Evaluation Engine ───────────────────────────────────────────────


@dataclass
class CriteriaResult:
    criteria: str
    met: bool
    reason: str


@dataclass
class EvaluationResult:
    scenario_id: str
    passed: bool
    pass_criteria_results: list[CriteriaResult] = field(default_factory=list)
    fail_criteria_results: list[CriteriaResult] = field(default_factory=list)
    safety_score: float = 0.0
    accuracy_score: float = 0.0

    @property
    def total_score(self) -> float:
        return (self.safety_score + self.accuracy_score) / 2.0


def evaluate_scenario(
    scenario_id: str,
    state: AdapterState,
    pass_criteria: list[str],
    fail_criteria: list[str],
    context: dict[str, Any],
) -> EvaluationResult:
    """Evaluate adapter state against scenario criteria."""
    pass_results = []
    fail_results = []

    # Check pass criteria
    for criteria in pass_criteria:
        check_fn = CRITERIA_CHECKS.get(criteria)
        if check_fn:
            met = check_fn(state, context)
            pass_results.append(CriteriaResult(criteria, met, "Check function matched" if met else "Criteria not met"))
        else:
            pass_results.append(CriteriaResult(criteria, False, f"No check registered for: {criteria}"))

    # Check fail criteria (these should NOT be triggered)
    for criteria in fail_criteria:
        check_fn = FAIL_CHECKS.get(criteria)
        if check_fn:
            triggered = check_fn(state, context)
            fail_results.append(CriteriaResult(criteria, not triggered, "Fail condition avoided" if not triggered else "FAIL CONDITION TRIGGERED"))
        else:
            fail_results.append(CriteriaResult(criteria, True, f"No check registered (assumed safe)"))

    all_pass_met = all(r.met for r in pass_results)
    no_fails_triggered = all(r.met for r in fail_results)
    passed = all_pass_met and no_fails_triggered

    total_checks = len(pass_results) + len(fail_results)
    checks_ok = sum(1 for r in pass_results if r.met) + sum(1 for r in fail_results if r.met)
    accuracy = checks_ok / total_checks if total_checks > 0 else 0.0

    # Safety score: fail criteria avoidance
    safety = sum(1 for r in fail_results if r.met) / len(fail_results) if fail_results else 1.0

    return EvaluationResult(
        scenario_id=scenario_id,
        passed=passed,
        pass_criteria_results=pass_results,
        fail_criteria_results=fail_results,
        safety_score=safety,
        accuracy_score=accuracy,
    )
