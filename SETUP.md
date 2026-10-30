# Connect to VS Code

The repository is already hosted on GitHub. **Do not create another repository or run `git init` in a new project folder.**

1. In VS Code press `Ctrl+Shift+P`.
2. Search for **Git: Clone**, then paste `https://github.com/saidzeki34/spaceapps-2026-earth-trend-detective.git`.
3. Choose a local folder and select **Open** when VS Code prompts you.
4. Use the branch selector at the bottom left, or press `Ctrl+Shift+P` → **Git: Checkout to...** → `develop`.
5. Invite teammates from GitHub repository **Settings → Collaborators and teams** using their GitHub usernames. Each should clone the same repository.

For reference, open a terminal via **Terminal → New Terminal** or `Ctrl+` ` (backtick), and use:
```powershell
git fetch origin
git switch develop
git pull --ff-only origin develop
```

During the event create new `feature/<issue>-<topic>` branches. Create PRs targeting `develop` rather than directly pushing into `main`.

Set appropriate branch rules under GitHub **Settings → Rules → Rulesets** if available. Block deletions and force pushes on `main`/`develop`; use PR review when supported. Confirm these rules are actually active. Store API keys in GitHub/Vercel/Supabase secrets, never in source control.
