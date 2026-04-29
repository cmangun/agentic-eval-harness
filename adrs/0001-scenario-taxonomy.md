# ADR-0001: Scenario taxonomy — five canonical classes

**Status**: Accepted
**Date**: 2026-04-28

## Context

The eval harness exists to test the verifiability properties of agent execution: did the agent deny what should have been denied, record what should have been recorded, fail safely under attack, and stay within declared bounds. The architectural choice is **how scenarios are classified** — what taxonomy organizes the test surface so that conformance vectors mean the same thing across implementations and so that adopters can locate the right scenario for the property they want to test.

A taxonomy too narrow excludes legitimate adopter concerns; a taxonomy too broad invites every implementer to invent their own classes, which destroys the comparability that makes conformance vectors useful in the first place. The deciding force is the conformance-vector contract: a scenario in `harness vendor A` must mean the same thing as a scenario in `harness vendor B` for cross-implementation validation to be meaningful.

A second force is lane clarity. The harness is one component in a six-component suite; its taxonomy must not pretend to cover threats the harness is not the right tool for (model-supply-chain attacks, training-data poisoning, etc.) and must not pull adopters away from primitives better solved elsewhere in the stack.

The deciding constraint is comparability across implementations plus clarity of lane.

## Decision

Five canonical scenario classes:

1. **Bypass** — the agent reaches a tool or surface without passing through policy.
2. **Injection** — adversarial input redirects the agent's behavior away from operator intent.
3. **Exfiltration** — the agent leaks data (PHI, PII, secrets) outside the bounded surface.
4. **Determinism** — the agent's behavior is non-reproducible under fixed inputs and policy.
5. **Budget** — the agent exceeds declared resource bounds (cost, time, tool-call count).

Sub-classifications and adopter-specific extensions are supported as `_experimental` extensions per `VERSIONING.md` §6 (the underscore-convention rule for non-canonical metadata). Experimental classes carry no stability guarantee through the v0.1 line.

## Alternatives Considered

- **Open taxonomy (adopters define their own classes)**: Maximally flexible; every adopter can shape the harness to their threat model. Rejected on cross-implementation comparability loss. If every adopter defines their own scenario classes, conformance vectors don't mean anything across implementations — a scenario tagged "Class B" in one harness has no relationship to "Class B" in another. The whole point of conformance vectors is comparable evaluation; an open taxonomy defeats it before any implementation is written.
- **Hierarchical taxonomy (broad classes with formal sub-classes)**: Comprehensive coverage with structured sub-classification. Rejected as premature complexity. v0.1 needs the five classes to be useful; sub-classification can come in v0.2 once the broad classes have field-tested edges and adopters have surfaced where the boundaries are unclear. Locking in a hierarchy now risks committing to the wrong tree shape — and re-hierarchizing later is breaking work that a flat taxonomy avoids.
- **OWASP LLM Top 10 alignment**: Externally anchored, broadly recognized in the LLM-security community, would inherit OWASP's audience and adoption curve. Rejected on scope mismatch. OWASP mixes runtime threats with evaluation concerns and includes entries — training-data poisoning, model-supply-chain attacks — that are out of scope for a runtime evaluation harness. Adopting OWASP wholesale would muddy the lane; the harness evaluates *agent execution*, not the model lifecycle. A focused taxonomy serves the harness better than an inherited one.

## Consequences

### Positive

- Conformance vectors mean the same thing across implementations. A scenario tagged "Bypass" in any compliant harness tests a bypass property defined identically.
- Lane clarity. The taxonomy makes explicit what the harness covers and (by what's not in the five classes) what it doesn't — model lifecycle, training data, deployment infrastructure are someone else's problem.
- Five classes is small enough to memorize and reason about; adopters do not need to consult a hierarchy before authoring a scenario.

### Negative

- Five classes is opinionated. Some adopters' threat models will need scenario types not in the canonical taxonomy — for example, agent-coordination failures in multi-agent systems, or specific regulatory-control mappings.
- The `_experimental` extension pattern lets adopters add classes without breaking conformance, with the understanding that experimental classes carry no stability guarantee per `VERSIONING.md` §6. Promotion from experimental to stable happens in a minor release after field testing.
- Adopters expecting an OWASP-aligned harness will need to map OWASP entries onto the five classes (where they map at all). Mapping table is a v0.2 documentation candidate.