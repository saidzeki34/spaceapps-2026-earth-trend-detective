# Mountain Water Availability

Shared project skeleton for the Oslo NASA Space Apps 2026 team, Earth System Trend Detective.

Preparation has ended. This branch contains project context, module responsibilities and **empty placeholders only**. Teammates will implement the code. There is no runnable application, model, integration or test suite.

The project direction is to investigate mountain-catchment water availability in Norway and Switzerland using river observations and relevant NASA environmental data, with historical context and clearly stated user requirements. Sources, scientific methods and the team's physics model require team decisions and implementation.

Read the [project brief](docs/project-brief.md), [module responsibilities](docs/architecture.md), [interface planning notes](docs/data-contracts.md) and [contribution workflow](CONTRIBUTING.md). Existing research notes remain reference material, not implemented capabilities.

## Main sections

| Folder under mountain_water/ | Planned scope | Timing |
| --- | --- | --- |
| ui/ | Controls, catchment overview, section views and charts | First phase |
| trend/ | Historical flow, reference periods, seasons, timing, change, variability and comparison | First phase |
| risk_assessment/ | Requirements, exposure, events and user/management context | Later |
| predictionmodel/ | Model inputs, scenarios, comparison baseline, team physics model and evaluation | Much later |

shared/ supports these sections with common contracts, configuration, data access, quality, catchments, coordination, caching and export. All files remain empty. See the [subsection and file guide](docs/architecture.md) for individual responsibilities.

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
