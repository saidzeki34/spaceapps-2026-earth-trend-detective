# Contributing

Main is the shared runnable foundation. Create small feature branches from current main and PRs to main. This supersedes the historical develop-based workflow. Preserve develop and work/* branches without resetting or force-pushing.

Agree one human owner per task. Reserved branch names are not permanent assignments. Everyone runs the same ExecuteProgram.py application.

| Workstream | Module boundary |
| --- | --- |
| Data/provenance | data, config |
| Flow/baseline | analysis/flow_metrics.py, baseline.py |
| Requirement exposure | analysis/risk.py |
| Trends/variability | analysis/trends.py, variability.py |
| Outlook/evaluation | models |
| UI/integration | ui, visualization, services |

Coordinate shared contracts.py changes. Use separate worktrees for concurrent writers. Do not commit someone else's files.

Before review, run Ruff and pytest; update contracts, methods and source ledger as needed. Include behavior, checks and unresolved limitations. Provider network checks are opt-in; mocks are not evidence of live access.

Merge PRs only after required checks and reviews; do not bypass protection. Human review is required for scientific claims. Automated tests do not validate scientific appropriateness. Label unreviewed results exploratory. Tag the exact tested demo commit.

Keep observations, caches, exports, credentials and local settings ignored. Attribute committed boundaries and metadata. Label synthetic fixtures and demo clearly. At handoff record owner, files, checks, provider coverage, limitations, PR and commit. See docs/task-checklist.md.
