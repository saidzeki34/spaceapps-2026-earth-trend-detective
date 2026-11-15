# Contributing

Main is the shared skeleton. Create small feature branches from current main and open PRs to main. This supersedes the historical develop-based integration workflow. Preserve develop and existing work/* branches; do not reset or force-push teammate branches.

Agree one human owner and file boundaries for each task. Reserved branch names do not assign ownership. Use separate worktrees for simultaneous writers and coordinate changes to shared contracts.

The main sections are mountain_water/ui and mountain_water/trend first, mountain_water/risk_assessment later, and mountain_water/predictionmodel much later. Common inputs and coordination live in mountain_water/shared. Agree edits to shared/contracts.py across section owners. Keep historical calculations out of UI files and do not make the first phase depend on deferred risk or prediction code.

The initial delivery contains documentation and empty placeholders only. Teammates will implement algorithms, providers, UI and models in separately assigned tasks. Do not import the archived generated application wholesale.

Keep PRs focused. Describe the problem, changed files, actual validation and unresolved questions. Honour required repository checks and reviews; do not bypass protections. Human review is required before presenting scientific claims as findings.

There are no application tests to run for the skeleton. Its administrative verification is the changed-file scope, zero-byte placeholders and documentation consistency. Do not report those as passing application tests.

Keep credentials, downloaded observations, local settings and caches out of commits. Document actual data/software/AI use and licences as work is added. Preserve missingness, units, provenance and temporal support in future interfaces.

Module responsibilities and unassigned team work are in docs/architecture.md and docs/task-checklist.md. Hand off the branch/commit, changed files, checks and remaining questions.
