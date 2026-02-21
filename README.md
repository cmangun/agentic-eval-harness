# agentic-eval-harness

A standardized evaluation harness for **agentic systems that must be verifiable**.

Runs a library of scenarios against an agent runtime and produces:
- Trace bundles (trace + receipts + artifacts)
- Metrics summaries (latency/cost/errors/tool calls)
- Evidence exports for reviewers

Receipt and bundle standards: [agentic-receipts](https://github.com/cmangun/agentic-receipts)

## Scenarios

| ID | Name | Tests |
|----|------|-------|
| S01 | Retrieval Under Policy | PHI redaction required |
| S02 | Tool Schema Enforcement | Invalid args must fail |
| S03 | Budget Cap | Stop/ask approval when exceeded |
| S04 | Human Approval Gate | Pause and request approval |
| S05 | Tool Failure Recovery | Retry + evidence |
| S06 | Policy Bypass Attempt | Must deny + record |
| S07 | Deterministic Run | Stable trace hash |
| S08 | Artifact Production | Manifest + verification |

## Quick Start

\`\`\`bash
make test
agentic-trace verify bundles/outputs/
\`\`\`

## Suite

This repo is part of the **Agentic Evidence Suite**:
- [agentic-receipts](https://github.com/cmangun/agentic-receipts) (standard)
- [agentic-trace-cli](https://github.com/cmangun/agentic-trace-cli) (tooling)
- [agentic-artifacts](https://github.com/cmangun/agentic-artifacts) (outputs)
- [agentic-policy-engine](https://github.com/cmangun/agentic-policy-engine) (governance)
- [agentic-eval-harness](https://github.com/cmangun/agentic-eval-harness) (scenarios)
- [agentic-evidence-viewer](https://github.com/cmangun/agentic-evidence-viewer) (review UI)

## License

MIT
