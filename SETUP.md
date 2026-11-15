# Getting the shared skeleton

Main is the team's starting point. Preparation has ended; the current repository delivery is documentation and empty placeholders.

```text
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feature/your-task
```

Inspect git status before switching branches and preserve uncommitted teammate work. Use a separate checkout/worktree for simultaneous writers. Existing develop and work/* branches are retained; do not reset them. PRs target main.

## Tools
Open the repository root in your preferred editor and read AGENTS.md. The repository does not prescribe editor extensions, a Dev Container or service connections. Git and access to this GitHub repository are sufficient to clone, pull and contribute; application tools can be chosen with future implementation tasks. No dependency installation is required for the empty skeleton.

There is no run, build or test command yet. ExecuteProgram.py, streamlit_app.py and module files are empty. Config and scripts folders contain tracking placeholders. Teammates should document dependency choices and commands in their implementation PRs.

Keep personal editor settings, credentials and account connections local. Repository-local cloud configuration has been removed. Separately installed GitHub apps and provider-side connections are managed outside the repository; deleting configuration files does not disconnect them.

## What was preserved
The former generated implementation is on archive/generated-implementation at 165e09b, separate from main. Its contents are outside the accepted skeleton scope. Existing research and the historical preparation record remain available. Local untracked teammate files are not part of the delivery.
