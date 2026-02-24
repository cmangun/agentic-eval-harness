"""Tests for the mock adapter — verifies PHI detection, schema validation, budget, retries, bypass."""
import pytest
from adapters.mock.adapter import MockAdapter


class TestPHIDetection:
    def test_detects_person_name(self):
        adapter = MockAdapter()
        findings = adapter.detect_phi("Patient John Doe needs treatment")
        names = [f for f in findings if f["type"] == "PERSON_NAME"]
        assert len(names) >= 1
        # Verify name-like patterns were detected (capitalized words)
        combined = " ".join(f["value"] for f in names)
        assert "John" in combined or "Doe" in combined

    def test_detects_ssn(self):
        adapter = MockAdapter()
        findings = adapter.detect_phi("SSN: 123-45-6789")
        ssns = [f for f in findings if f["type"] == "SSN"]
        assert len(ssns) == 1
        assert ssns[0]["value"] == "123-45-6789"

    def test_detects_dob(self):
        adapter = MockAdapter()
        findings = adapter.detect_phi("DOB 01/15/1980")
        dobs = [f for f in findings if f["type"] == "DATE_OF_BIRTH"]
        assert len(dobs) == 1

    def test_redacts_phi(self):
        adapter = MockAdapter()
        text = "Patient John Doe SSN 123-45-6789"
        findings = adapter.detect_phi(text)
        redacted = adapter.redact_phi(text, findings)
        assert "John Doe" not in redacted
        assert "123-45-6789" not in redacted
        assert "REDACTED" in redacted

    def test_no_phi_in_clean_text(self):
        adapter = MockAdapter()
        findings = adapter.detect_phi("check eligibility for plan code ABC123")
        # May find some false positives but should not find SSN/DOB
        ssns = [f for f in findings if f["type"] == "SSN"]
        assert len(ssns) == 0


class TestSchemaValidation:
    def test_valid_tool_call(self):
        adapter = MockAdapter()
        valid, msg = adapter.validate_tool_call("search", {"query": "test"})
        assert valid
        assert msg == "Valid"

    def test_missing_required_param(self):
        adapter = MockAdapter()
        valid, msg = adapter.validate_tool_call("lookup_benefits", {"benefit_code": "MED001"})
        assert not valid
        assert "member_id" in msg

    def test_wrong_type(self):
        adapter = MockAdapter()
        valid, msg = adapter.validate_tool_call("search", {"query": 123})
        assert not valid
        assert "expected str" in msg

    def test_unknown_tool(self):
        adapter = MockAdapter()
        valid, msg = adapter.validate_tool_call("nonexistent", {})
        assert not valid
        assert "Unknown tool" in msg


class TestBudget:
    def test_budget_tracking(self):
        adapter = MockAdapter({"budget_limit": 1.0, "cost_per_call": 0.05})
        adapter.execute("query", {"query": "test"})
        assert adapter.state.budget_tracked

    def test_budget_exceeded(self):
        adapter = MockAdapter({"budget_limit": 0.01, "cost_per_call": 0.05})
        adapter.execute("query", {"query": "test"})
        assert adapter.state.budget_exceeded
        assert adapter.state.approval_requested

    def test_budget_within_limits(self):
        adapter = MockAdapter({"budget_limit": 10.0, "cost_per_call": 0.05})
        adapter.execute("query", {"query": "test"})
        assert not adapter.state.budget_exceeded


class TestRetry:
    def test_retries_recorded(self):
        adapter = MockAdapter()
        adapter.execute("query", {"simulate_failure": True, "max_retries": 3, "query": "test"})
        assert len(adapter.state.retries) == 3
        assert adapter.state.retries[0]["attempt"] == 1
        assert adapter.state.retries[2]["success"] is True

    def test_no_retry_without_failure(self):
        adapter = MockAdapter()
        adapter.execute("query", {"query": "test"})
        assert len(adapter.state.retries) == 0


class TestBypass:
    def test_all_bypass_strategies_denied(self):
        adapter = MockAdapter()
        strategies = ["omit_context", "rename_action", "direct_tool_call"]
        adapter.execute("query", {"bypass_strategies": strategies, "query": "test"})
        assert len(adapter.state.bypass_attempts_denied) == 3
        deny_receipts = [r for r in adapter.state.policy_receipts if r.decision == "deny"]
        assert len(deny_receipts) == 3

    def test_no_bypass_without_strategies(self):
        adapter = MockAdapter()
        adapter.execute("query", {"query": "test"})
        assert len(adapter.state.bypass_attempts_denied) == 0


class TestDeterminism:
    def test_same_input_same_hash(self):
        a1 = MockAdapter()
        a2 = MockAdapter()
        ctx = {"query": "deterministic test", "seed": 42}
        a1.execute("query", dict(ctx))
        a2.execute("query", dict(ctx))
        assert a1.state.trace_hash == a2.state.trace_hash
        assert a1.state.trace_hash != ""


class TestArtifacts:
    def test_artifact_produced(self):
        adapter = MockAdapter()
        adapter.execute("query", {"produce_artifact": True, "query": "test"})
        assert len(adapter.state.artifacts) == 1
        artifact = adapter.state.artifacts[0]
        assert artifact["manifest_valid"]
        assert artifact["hash"]
        assert artifact["provenance_trace"] == adapter.state.trace_hash
