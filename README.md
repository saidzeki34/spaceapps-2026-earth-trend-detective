# Mountain Water Availability

Shared project skeleton for the Oslo NASA Space Apps 2026 team, Earth System Trend Detective.

Preparation has ended. This branch contains project context, module responsibilities and **empty placeholders only**. Teammates will implement the code. There is no runnable application, model, integration or test suite.

The project direction is to investigate mountain-catchment water availability in Norway and Switzerland using river observations and relevant NASA environmental data, with historical context and clearly stated user requirements. Sources, scientific methods and the team's physics model require team decisions and implementation.

Read the [project brief](docs/project-brief.md), [module responsibilities](docs/architecture.md), [interface planning notes](docs/data-contracts.md) and [contribution workflow](CONTRIBUTING.md). Existing research notes remain reference material, not implemented capabilities.

## Start a teammate branch

```text
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feature/your-task
```

Preserve uncommitted work first. Use a separate worktree when another person or agent is working in your checkout. PRs target main.

The agreed Python/Streamlit entry points and module files are intentionally zero bytes. Do not expect ExecuteProgram.py or streamlit_app.py to launch anything. The tests folder is empty apart from its tracking placeholder. See [SETUP.md](SETUP.md).

Earlier generated implementation is preserved on [archive/generated-implementation](https://github.com/saidzeki34/spaceapps-2026-earth-trend-detective/tree/archive/generated-implementation), commit 165e09b. It was never merged into main. It is an archive, not the accepted foundation; do not merge it wholesale.

The team owns subsequent code, methods and data choices. No deployment is included.
