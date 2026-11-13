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

## Prepared editor environment

After pulling the preparation changes into your checkout, open the repository root in VS Code and run **Extensions: Show Recommended Extensions**. Install the workspace recommendations. They include Codex, Claude Code, Python/Jupyter, ESLint, Prettier, GitHub PRs, Live Share, EditorConfig and Dev Containers. A recommendation file does not itself install extensions on your computer.

Optional: use **Dev Containers: Reopen in Container** with Docker, or open this branch in GitHub Codespaces. The configuration installs Node 22, Python 3.12 and editor extensions. It does not scaffold an application, install application dependencies, run data analysis, start a server or deploy anything. Codespaces usage can consume your account quota. The container build has not been executed in the preparation environment because Docker is unavailable there.

Sign into Codex and Claude with your own accounts. Do not share account tokens. Codex reads AGENTS.md; CLAUDE.md imports it for Claude. Start both tools in this repository root. Cloud agents need access to this repository and the branch containing these files; the files do not grant account access automatically. A Dev Container does not configure every hosted Codex/Claude runtime.

## Supabase and Vercel connections

These are official remote MCP connections, not application SDKs. Repository definitions are in .mcp.json (Claude) and .codex/config.toml (Codex). Codex project settings apply only after the checkout is trusted. Review the definitions and authenticate through the relevant client; credentials stay outside Git.

| Connection | Prepared state | What remains |
| --- | --- | --- |
| Supabase | Documentation-only feature group, read_only=true | Client trust/OAuth if requested; project access is deliberately absent |
| Vercel | Official endpoint, disabled in both clients | Enable after competition start, authenticate and confirm the correct team/project |

No Supabase or Vercel project was created, linked, queried or deployed by this preparation. No GitHub App installation or dashboard environment variables were changed. No credentials or project IDs are assumed.

After the official start and team instruction:
1. Confirm the intended Supabase project and Vercel team/project. Create them only if needed and authorized.
2. For Supabase, replace the docs-only URL with the official project-scoped URL containing project_ref and read_only=true. Start with docs,database features; retain read-only access until a specific write task is authorized. Do not use organization-wide default access.
3. For Vercel, set enabled=true in .codex/config.toml and remove vercel from disabledMcpjsonServers in .claude/settings.json. Authenticate with Codex's MCP login flow or Claude's /mcp menu. Inspect the available tools before using them.
4. Verify account/target access with a harmless read. Record success or the precise failure; configuration alone is not a connection test.
5. Choose the framework during the event. Then install its SDKs/CLI dependencies and implement the app. If importing the repo into Vercel, inspect production/preview settings and automatic deployments before proceeding.
6. Keep Supabase secret/service_role keys server-only. Browser publishable keys require correctly configured access policies. Do not put database passwords, Earthdata credentials, NOAA tokens or Vercel tokens in frontend environment variables or Git. Set real environment variables in the platform's secret UI or ignored local files.

References: [Codex MCP](https://developers.openai.com/codex/mcp/), [Claude memory](https://code.claude.com/docs/en/memory), [Claude MCP](https://code.claude.com/docs/en/mcp), [Supabase MCP](https://supabase.com/docs/guides/ai-tools/mcp), [Supabase keys](https://supabase.com/docs/guides/getting-started/api-keys), [Vercel MCP](https://vercel.com/docs/agent-resources/vercel-mcp), [Vercel GitHub integration](https://vercel.com/docs/git/vercel-for-github).

## Starting a later AI session

Ask the agent to read AGENTS.md and its linked research notes, report the current preparation restriction, identify source-access gaps, and wait for a task. Once the event starts, explicitly authorize the first implementation task. Do not ask two agents to edit the same checkout concurrently.

Reserved work/* branches may predate this preparation. Before using one, fetch origin and merge origin/develop without rewriting history, or preferably create a fresh feature branch from updated develop. Never reset a teammate's branch to make it match.
