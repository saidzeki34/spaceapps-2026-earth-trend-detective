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
Open the repository root in your editor and read AGENTS.md. Existing editor recommendations, optional container configuration and documentation connections are retained from the administrative setup. Their presence does not select application dependencies or authorize cloud operations. No new dependency installation is required for this skeleton.

There is no run, build or test command yet. ExecuteProgram.py, streamlit_app.py and module files are empty. Config and scripts folders contain tracking placeholders. Teammates should document dependency choices and commands in their implementation PRs.

Supabase access remains documentation-only; Vercel remains disabled. Do not enable services or deploy as part of obtaining the skeleton. Keep credentials and account-local settings out of Git.

## What was preserved
The former generated implementation is on archive/generated-implementation at 165e09b, separate from main. Its contents are outside the accepted skeleton scope. Existing research and the historical preparation record remain available. Local untracked teammate files are not part of the delivery.
