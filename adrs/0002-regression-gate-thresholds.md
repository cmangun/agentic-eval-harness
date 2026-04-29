# ADR-0002: Regression gate thresholds — per-scenario pass/fail with named rationale

**Status**: Accepted
**Date**: 2026-04-28

## Context

The eval harness produces results that gate CI builds and release approvals. Each scenario, when run against an agent under test, produces an outcome that downstream tooling (CI runner, release dashboard, regression gate) interprets as pass-or-fail for the build. The architectural choice is **how the gate threshold is computed** — what mathematical or comparative shape the outcome takes, and what triggers a regression alarm.

Three families of approaches exist. **Boolean** outcomes — each scenario passes or fails its assertions, full stop. **Statistical** outcomes — current run compared against a baseline of previous runs, with anomalies flagged when the deviation exceeds a threshold. **Composite** outcomes — a weighted score across all scenarios, with regression triggered when the score falls below a target.

Each shape has different diagnostic properties. Boolean outcomes are precise (the failing scenario is named, its assertion is named, the recovery action is locatable) but brittle to flaky scenarios. Statistical outcomes are forgiving of noise but produce alarms with weak diagnostic signal. Composite outcomes give a single number per run but tell you nothing about *which* scenario regressed.

The deciding constraint is that regression gates need to fail loudly and locate the regression precisely. A gate that fails without locating the failure forces engineering investigation before any fix can begin; a gate that fails statistically forces the same investigation plus a separate "is this a real regression or noise" judgment call.

## Decision

Pass/fail per scenario. Boolean outcomes. No statistical baselines, no time-window comparisons, no composite scores. Each scenario carries a named rationale stating what failure indicates and what the recovery action is. A build's regression gate fails if any scenario fails; the failure surfaces the specific scenario name, its assertion, and its rationale.

## Alternatives Considered

- **Statistical baseline (current run vs. previous N runs)**: Anomaly detection over the rolling history of runs; alarms fire when current run deviates from baseline by more than a configurable threshold. Rejected because regression scenarios should be deterministic. If a scenario was passing yesterday and is failing today, that's a regression — full stop. Statistical noise belongs in observability metrics, not in security regression gates. A scenario whose pass/fail varies run-to-run is a flaky scenario, not a real signal — and flaky scenarios are an authoring bug to fix, not a noise floor to live with.
- **Time-window comparison (this week vs. last week)**: Drift detection over longer windows; alarms fire when failure rate increases relative to a recent baseline. Rejected on the same reasoning. A scenario either passes its assertions or it doesn't. If failure rate creeps up over time, individual scenarios are failing and should be investigated individually; smoothing the failures into a trendline obscures which scenarios are actually regressing.
- **Composite score (weighted across scenarios)**: Single number per run; regression triggered when the score falls below a target. Rejected on diagnostic-signal loss. A composite that says "you scored 8.4 this week, 8.7 last week" tells you nothing about *which scenario* regressed. The engineering team has to drill into per-scenario data anyway to find the actual regression. Per-scenario pass/fail surfaces the specific failure with a specific recovery action immediately, without the composite-score intermediate step.

## Consequences

### Positive

- Regression gates locate failures precisely. The failing scenario, its assertion, and its rationale are surfaced together; the engineering response starts with diagnosis, not search.
- Determinism becomes a scenario-authoring property. A scenario is correct if it passes deterministically and fails deterministically; flakiness is detectable as an authoring bug rather than absorbed as noise.
- The gate's contract is unambiguous: a build either passes every scenario or it fails. There is no "partial pass" or "acceptable degradation" interpretation that downstream tooling has to reconcile.

### Negative

- Brittleness. Flaky scenarios produce false-positive failures, which erode trust in the gate. Mitigation: scenario-design discipline — deterministic inputs, bounded outputs, no time-dependent assertions, no dependency on external state outside the harness's control. Authoring methodology is documented in ADR-0003 below.
- The gate does not surface "this scenario was 90% passing and is now 70% passing" patterns. An adopter who wants that signal builds it on top of the per-scenario outcomes (the harness emits the data; the trend analysis is downstream).
- Adopters whose threat models include genuinely probabilistic phenomena (LLM completion variability, for example) need to design scenarios around the determinism property — wrapping non-deterministic primitives in bounded assertions rather than letting probability into the gate itself.