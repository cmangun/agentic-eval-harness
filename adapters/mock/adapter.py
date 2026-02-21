"""Mock agent adapter with deterministic outputs."""
from dataclasses import dataclass
from typing import Any

@dataclass
class MockResponse:
    content: str
    tool_calls: list[dict]
    tokens_used: int
    latency_ms: float

class MockAdapter:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.call_count = 0

    def execute(self, action: str, context: dict[str, Any]) -> MockResponse:
        self.call_count += 1
        return MockResponse(f"Mock: {action}", [], 100, 50.0)

    def reset(self): self.call_count = 0
