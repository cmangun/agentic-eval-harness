"""Configurable mock agent adapter with realistic behavior simulation."""
import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any


PHI_PATTERNS = [
    (r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", "PERSON_NAME"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
    (r"\b\d{2}/\d{2}/\d{4}\b", "DATE_OF_BIRTH"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL"),
    (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "PHONE"),
    (r"\b\d{1,5}\s\w+\s(?:St|Ave|Blvd|Rd|Dr|Ln|Way)\b", "ADDRESS"),
    (r"\bMRN[-:]?\s*\d{6,}\b", "MEDICAL_RECORD"),
]


@dataclass
class MockResponse:
    content: str
    tool_calls: list[dict]
    tokens_used: int
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyReceipt:
    policy_id: str
    decision: str
    reason: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class AdapterState:
    """Tracks all decisions and events during execution."""
    phi_detected: list[dict] = field(default_factory=list)
    phi_redacted: bool = False
    policy_receipts: list[PolicyReceipt] = field(default_factory=list)
    tool_calls_made: list[dict] = field(default_factory=list)
    tool_calls_rejected: list[dict] = field(default_factory=list)
    budget_tracked: bool = False
    budget_remaining: float = 0.0
    budget_exceeded: bool = False
    approval_requested: bool = False
    execution_paused: bool = False
    retries: list[dict] = field(default_factory=list)
    bypass_attempts_denied: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    trace_hash: str = ""
    total_tokens: int = 0
    total_cost: float = 0.0


TOOL_SCHEMAS = {
    "search": {
        "required": ["query"],
        "types": {"query": str, "limit": int, "offset": int},
    },
    "lookup_benefits": {
        "required": ["member_id", "benefit_code"],
        "types": {"member_id": str, "benefit_code": str},
    },
    "submit_claim": {
        "required": ["claim_id", "amount", "provider_id"],
        "types": {"claim_id": str, "amount": float, "provider_id": str},
    },
}


class MockAdapter:
    """Configurable mock that simulates real agent behaviors for evaluation."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.state = AdapterState()
        self.call_count = 0
        self._budget_limit = self.config.get("budget_limit", 10.0)
        self._cost_per_call = self.config.get("cost_per_call", 0.05)
        self.state.budget_remaining = self._budget_limit

    def reset(self):
        self.call_count = 0
        self.state = AdapterState()
        self.state.budget_remaining = self._budget_limit

    def detect_phi(self, text: str) -> list[dict]:
        findings = []
        for pattern, phi_type in PHI_PATTERNS:
            for match in re.finditer(pattern, text):
                findings.append({
                    "type": phi_type,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                })
        return findings

    def redact_phi(self, text: str, findings: list[dict]) -> str:
        redacted = text
        for finding in sorted(findings, key=lambda f: f["start"], reverse=True):
            placeholder = f"[REDACTED_{finding['type']}]"
            redacted = redacted[:finding["start"]] + placeholder + redacted[finding["end"]:]
        return redacted

    def validate_tool_call(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        schema = TOOL_SCHEMAS.get(tool_name)
        if not schema:
            return False, f"Unknown tool: {tool_name}"
        for req in schema["required"]:
            if req not in args:
                return False, f"Missing required parameter: {req}"
        for key, value in args.items():
            expected_type = schema["types"].get(key)
            if expected_type and not isinstance(value, expected_type):
                return False, f"Parameter '{key}' expected {expected_type.__name__}, got {type(value).__name__}"
        return True, "Valid"

    def check_budget(self, cost: float) -> tuple[bool, str]:
        self.state.budget_tracked = True
        if self.state.budget_remaining - cost < 0:
            self.state.budget_exceeded = True
            return False, f"Budget exceeded: remaining={self.state.budget_remaining:.2f}, requested={cost:.2f}"
        return True, "Within budget"

    def consume_budget(self, cost: float):
        self.state.budget_remaining -= cost
        self.state.total_cost += cost

    def detect_bypass(self, action: str, context: dict[str, Any]) -> bool:
        strategies = context.get("bypass_strategies", [])
        for strategy in strategies:
            reason_map = {
                "omit_context": "Context omission detected — policy requires full context",
                "rename_action": "Action renaming detected — policy enforces canonical names",
                "direct_tool_call": "Direct tool bypass detected — all calls must route through policy engine",
            }
            reason = reason_map.get(strategy, f"Unknown bypass strategy '{strategy}' denied by default")
            self.state.bypass_attempts_denied.append({"strategy": strategy, "reason": reason})
            self.state.policy_receipts.append(PolicyReceipt(
                policy_id=f"bypass_deny_{strategy}",
                decision="deny",
                reason=f"Bypass attempt via {strategy} denied",
            ))
        return len(strategies) > 0

    def execute(self, action: str, context: dict[str, Any]) -> MockResponse:
        self.call_count += 1
        start = time.monotonic()

        # PHI detection and redaction
        if "query" in context:
            phi = self.detect_phi(context["query"])
            if phi:
                self.state.phi_detected = phi
                context["query"] = self.redact_phi(context["query"], phi)
                self.state.phi_redacted = True
                self.state.policy_receipts.append(PolicyReceipt(
                    policy_id="phi_redaction", decision="allow",
                    reason=f"PHI detected and redacted: {len(phi)} findings",
                ))

        # Tool schema enforcement
        if "tool_call" in context:
            tool = context["tool_call"]
            valid, msg = self.validate_tool_call(tool.get("name", ""), tool.get("args", {}))
            if valid:
                self.state.tool_calls_made.append(tool)
            else:
                self.state.tool_calls_rejected.append({"tool": tool, "reason": msg})
                self.state.policy_receipts.append(PolicyReceipt(
                    policy_id="schema_enforcement", decision="deny", reason=msg,
                ))

        # Budget check
        budget_ok, budget_msg = self.check_budget(self._cost_per_call)
        if budget_ok:
            self.consume_budget(self._cost_per_call)
        else:
            self.state.approval_requested = True
            self.state.policy_receipts.append(PolicyReceipt(
                policy_id="budget_cap", decision="require_approval", reason=budget_msg,
            ))

        # Approval gate
        if context.get("requires_approval"):
            self.state.execution_paused = True
            self.state.approval_requested = True
            self.state.policy_receipts.append(PolicyReceipt(
                policy_id="human_approval_gate", decision="require_approval",
                reason="Action requires human approval before execution",
            ))

        # Tool failure + retry
        if context.get("simulate_failure"):
            max_retries = context.get("max_retries", 3)
            for attempt in range(max_retries):
                self.state.retries.append({
                    "attempt": attempt + 1,
                    "success": attempt == max_retries - 1,
                    "timestamp": time.time(),
                })
            self.state.policy_receipts.append(PolicyReceipt(
                policy_id="tool_recovery", decision="allow",
                reason=f"Recovered after {max_retries} attempts",
            ))

        # Bypass detection
        if "bypass_strategies" in context:
            self.detect_bypass(action, context)

        # Deterministic trace hash
        trace_input = f"{action}:{sorted(context.items())}"
        self.state.trace_hash = hashlib.sha256(trace_input.encode()).hexdigest()

        # Artifact production
        if context.get("produce_artifact"):
            artifact_content = f"Artifact for {action}"
            artifact_hash = hashlib.sha256(artifact_content.encode()).hexdigest()
            self.state.artifacts.append({
                "name": f"{action}_output",
                "hash": artifact_hash,
                "manifest_valid": True,
                "provenance_trace": self.state.trace_hash,
            })

        tokens = context.get("tokens", 100)
        self.state.total_tokens += tokens
        duration = (time.monotonic() - start) * 1000

        return MockResponse(
            content=f"Executed: {action}",
            tool_calls=self.state.tool_calls_made,
            tokens_used=tokens,
            latency_ms=duration,
            metadata={
                "phi_findings": len(self.state.phi_detected),
                "policy_receipts": len(self.state.policy_receipts),
                "trace_hash": self.state.trace_hash,
            },
        )
