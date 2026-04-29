# ADR-0003: Red-team scenario authoring methodology — adversarial intent, assertion, bounds

**Status**: Accepted
**Date**: 2026-04-28

## Context

The eval harness derives its value from the scenarios it runs. A scenario is the unit of testable assertion — adversarial intent translated into a runnable check against an agent under test. The architectural choice is **what makes a scenario complete enough** to be portable across implementations and to be interpreted consistently by downstream tooling.

Two failure modes shape the design. **Under-specification**: a scenario that lacks structural elements is not portable — different implementers reading the same scenario draw different conclusions about what passing looks like, which scenario class it belongs to, and whether their interpretation matches the original author's intent. **Over-specification**: a scenario that locks down every operational detail (specific input strings, specific tool names, specific model versions) is not adaptable across the agent runtimes the harness is meant to test.

The methodology must produce scenarios that are simultaneously **portable** (interpretable consistently across implementations) and **specific** (concrete enough to test something real). The deciding constraint is that scenarios need to be portable across implementations and explicit about what they test (and don't test).

## Decision

Every scenario must specify three required elements:

1. **Adversarial intent**, in plain language. What is the adversary trying to accomplish? Example: *"Submit a tool call that bypasses the policy gate via parameter smuggling."*
2. **Assertion**. What does passing look like? Usually one of: *"verifier rejects bundle,"* *"policy denies action,"* or *"evaluation harness flags regression."*
3. **Bounds**. What the scenario does NOT test. Example: *"This scenario does not test prompt-injection of the LLM itself; injection attacks are scenario-class 02."*

The three required elements are documented as a scenario-authoring template at `agentic-eval-harness/docs/scenario-design.md`. Authoring tooling (linters, scaffolding generators) checks for the three elements before a scenario is admitted to the harness.

## Alternatives Considered

- **Free-form scenario description with example inputs**: Minimal structure; authors describe the scenario in prose and provide example inputs for the runner. Rejected on conformance-vector incompatibility. Free-form scenarios can't be ported across implementations cleanly; one harness implementer interprets a prose description differently from another, and the methodology has to specify what makes a scenario *complete* enough to run elsewhere with the same pass/fail interpretation. Free-form leaves that question to the reader.
- **Adopt an existing framework (garak, PyRIT)**: Externally defined methodologies for LLM-attack scenario authoring, with established communities and tool ecosystems. Rejected on scope mismatch. garak, PyRIT, and similar frameworks focus on model-level attacks — jailbreaking, prompt-injection variants, prompt-stealing. Agentic systems have a wider threat surface — policy bypass, redaction misuse, budget exhaustion, determinism violations — that LLM-attack frameworks don't model. Wrong shape for the harness; the eval-harness lane sits one layer above where these frameworks operate.
- **Property-based testing only**: Generative approach where the harness produces scenarios from properties; no manually authored scenarios. Rejected on missing the documentation contract. Property-based testing is excellent for *finding* unknown failures by exploring large input spaces. Red-team scenarios document *known* failure modes that must continue to be detected — they encode "we already know this can break; verify it stays unbroken." Different jobs. Property-based testing may augment in v0.2 as a separate generation pipeline that produces scenarios alongside the manual ones.

## Consequences

### Positive

- Scenarios are portable across implementations. The three required elements give every implementer the same interpretation of what passing looks like; conformance-vector exchange between harnesses becomes meaningful.
- Bounds are explicit. Adopters reading a scenario know what it tests and what it doesn't, which prevents the common failure of one scenario being misinterpreted as covering a class it doesn't.
- The template at `agentic-eval-harness/docs/scenario-design.md` makes authoring tractable for new contributors; the methodology is teachable rather than tacit.

### Negative

- More rigor at scenario-authoring time. Authors cannot dash off a quick scenario; the three required elements force a discipline that takes longer than free-form description. Acceptable: scenario authoring is a once-per-scenario cost, while scenario interpretation is a per-run cost across many runs and many implementations.
- Less ad-hoc red-teaming. An engineer who wants to "see what happens" with an attack vector cannot simply add a scenario without filling in the three elements. Mitigation: the harness supports an experimental scaffold where partial scenarios run for exploration, with a clear gate before promotion to the canonical scenario library.
- Property-based testing is not part of v0.1's authoring path. Adopters wanting generative scenario discovery wait for v0.2 or implement it as a separate pipeline whose output feeds into the canonical authoring methodology after manual review.