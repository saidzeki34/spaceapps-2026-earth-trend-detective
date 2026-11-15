# Contributing

Main combines the team's work. UI and integration branches start from main and PRs target main. Backend contributors retain their documented workflow: feature branches start from origin/work/backend, PRs target work/backend, and accepted backend changes reach main through an integration PR. This supersedes the historical develop-based workflow. Preserve all original branches; do not reset or force-push teammate branches.

Agree one human owner and file boundaries for each task. Reserved branch names do not assign ownership. Use separate worktrees for simultaneous writers and coordinate changes to shared contracts.

The main sections are mountain_water/ui and mountain_water/trend first, mountain_water/risk_assessment later, and mountain_water/predictionmodel much later. Common inputs and coordination live in mountain_water/shared. Agree edits to shared/contracts.py across section owners. Keep historical calculations out of UI files and do not make the first phase depend on deferred risk or prediction code.

The initial delivery contained documentation and empty placeholders. Main now includes Jonathan's Swiss/Norwegian backend and Claude's submitted local web UI. The UI reads saved Swiss results and contains explicitly labelled imaginary stand-ins; backend Norway/station features and the dedicated risk/prediction modules still need UI integration or implementation. Teammates continue separately assigned work. Do not import the archived generated application wholesale.

Keep PRs focused. Describe the problem, changed files, actual validation and unresolved questions. Honour required repository checks and reviews; do not bypass protections. Human review is required before presenting scientific claims as findings.

Run the existing backend tests with python -m pytest after installing the dev dependencies; see SETUP.md. Check the UI separately when it changes. Preserve placeholder modules that remain unimplemented. State which checks actually ran; a source merge does not establish scientific validity or live API availability.

Keep credentials, downloaded observations, local settings and caches out of commits. Document actual data/software/AI use and licences as work is added. Preserve missingness, units, provenance and temporal support in future interfaces.

Module responsibilities and unassigned team work are in docs/architecture.md and docs/task-checklist.md. Hand off the branch/commit, changed files, checks and remaining questions.
