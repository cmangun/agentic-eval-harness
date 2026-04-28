# Non-goals

What `agentic-eval-harness` deliberately does not try to be. Each item draws an explicit boundary against layers it tests rather than replaces.

## Not a runtime governance layer

The harness uses `agentic-policy-engine` as the gate under test; it does not replace it. Production governance happens in the policy engine running inline with execution. The harness verifies that the gate's properties hold against bypass scenarios — it is the test, not the enforcement.

## Not a unit-test framework

Scenarios are pass/fail contracts against the verifiability properties of an agent under test (did it deny? did it record? did the receipt chain stay valid?). They are not arbitrary assertions about internal state, return values, or function behavior. Adopters keep their unit-test framework for those concerns.

## Not a model-quality oracle

The harness tests verifiability and bypass resistance, not whether the agent's task outputs are correct. A model that consistently produces verifiable-but-wrong recommendations passes harness scenarios while failing the actual task. Quality belongs to a separate evaluation discipline (benchmarks, human-in-the-loop review, domain-specific scoring).

## Not a prompt-injection detector at runtime

The harness exercises injection scenarios *during testing* and records the agent's response under attack. It does not detect or prevent injection during production runs. Runtime detection is a different layer of the stack with its own primitives.

## Not a security scanner

The harness probes the receipt-emission contract, the policy boundary, and scenario-specific resistance. It is not a general-purpose security testing tool — it does not scan dependencies, fuzz arbitrary inputs, audit infrastructure, or test for vulnerability classes outside its scenario taxonomy. The five canonical scenario classes (bypass, injection, exfiltration, determinism, budget) define its scope.
