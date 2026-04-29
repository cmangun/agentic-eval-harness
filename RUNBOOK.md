# Runbook

> Operational guide for `agentic-eval-harness`. The harness is a CI-time component, not a runtime service; metrics and recovery procedures here cover the CI pipeline's interaction with the harness as the v0.1 line matures toward v1.0. Adopters tune thresholds to their CI environment.

## Metrics

The harness should expose the following metrics during and after each run:

- **Scenario pass rate** — fraction of scenarios in the canonical suite that pass per run. Per [adrs/0002-regression-gate-thresholds.md](adrs/0002-regression-gate-thresholds.md), the regression gate is per-scenario boolean; the aggregate metric is informational only and never used as a gate threshold itself.
- **Regression count per release** — number of scenarios that pass on the prior commit and fail on the current commit. Tracks introduction of bypass paths and policy-enforcement degradation.
- **Scenario duration distribution** — wall-clock time per scenario. Track p50/p95/p99 across the suite. Recommended budget: p99 ≤ 60s per scenario; runs that exceed are candidates for refactoring or splitting.
- **Harness queue depth** — when running scenarios in parallel, the depth of pending work. Spikes indicate concurrency misconfiguration or single-point-of-contention scenarios.
- **CI total runtime** — full canonical suite wall-clock time. Recommended target: 5–15 minutes for a 50-scenario suite at default concurrency.

## Performance envelope

Expected behavior in typical CI deployments:

- **Concurrency**: scenarios run sequentially by default; parallel execution is operator-configurable. Per-scenario state isolation must hold under any concurrency level the operator chooses.
- **Per-scenario timeout**: 60 seconds default. Operators tune per scenario class — bypass scenarios may need longer; determinism scenarios shorter. Timeouts trigger scenario failure per [adrs/0002-regression-gate-thresholds.md](adrs/0002-regression-gate-thresholds.md).
- **Full canonical suite**: 5–15 minutes for a 50-scenario suite at default concurrency. Scales linearly with scenario count and inversely with concurrency level.
- **Resource footprint**: dominated by the agent under test, not the harness itself. The harness is a thin orchestrator; the runtime cost lives in the system being evaluated.

## Failure modes

The harness has four named failure modes:

- **Scenario timeout** — a scenario exceeds its declared per-scenario budget. Distinct from scenario assertion failure; timeout means the scenario did not reach an assertion.
- **Agent under test unavailable** — the system being evaluated is unreachable, returns connection errors, or fails to initialize. The harness cannot proceed without the system.
- **Harness crash mid-run** — the harness process dies (memory pressure, killed signal, panic) before the run completes. Partial results may exist on disk; the run is structurally incomplete.
- **Conformance vector check failure** — the harness depends on `agentic-receipts` conformance vectors for receipt-shape validation. Vector load failure or mismatched vector versions block the run before scenarios start.

## Recovery procedures

Recovery responses, per failure mode:

- **Scenario timeout**: mark the scenario failed per [adrs/0002-regression-gate-thresholds.md](adrs/0002-regression-gate-thresholds.md) (regression gate is per-scenario boolean — pass/fail, no statistical baseline). Surface the specific scenario in CI output alongside its declared budget; engineers diagnose and either fix the scenario authoring or fix the underlying system slowness. Repeated timeouts on the same scenario are an authoring bug, not a noise floor.
- **Agent under test unavailable**: mark the entire suite failed with an `infrastructure` reason rather than a `regression` reason — the gate distinguishes "agent broken" from "agent regressed." CI logs surface the connection error or initialization failure; engineers fix infrastructure before re-running. Do not interpret an infrastructure failure as a passing test ([adrs/0002-regression-gate-thresholds.md](adrs/0002-regression-gate-thresholds.md) forbids ambiguous-default outcomes).
- **Harness crash mid-run**: re-run the suite from the start. The harness does not maintain a scenario-level checkpoint mechanism in v0.1; partial results from the crashed run are discarded. Operators investigating crash patterns examine harness memory profile and per-scenario isolation; persistent crashes block the release until root-caused.
- **Conformance vector check failure**: block the release. The harness refuses to score scenarios when its receipt-validation primitive is broken — a scenario that cannot validate the receipts it produces cannot deliver a meaningful pass/fail. Engineers update the conformance vectors (tracked in `agentic-receipts/vectors/`) or pin the harness to a known-good vector version per [`VERSIONING.md` §3](https://github.com/cmangun/agentic-evidence/blob/main/VERSIONING.md) of the meta-repo's compatibility matrix.
