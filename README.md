# Mountain Water Availability

Shared project for the Oslo NASA Space Apps 2026 team, Earth System Trend Detective.

Preparation has ended. Main combines Jonathan's Swiss/Norwegian trend backend and station comparisons with Claude's submitted RivaScope web UI. The UI reads saved Swiss CAMELS-CH results and uses clearly labelled imaginary data where inputs or models are missing. Norway and station comparisons are available through the backend CLI but are not yet connected to the UI. See the [submitted handoffs](docs/submitted-handoffs.md) for preserved branches and limitations.

The project direction is to investigate mountain-catchment water availability in Norway and Switzerland using river observations and relevant NASA environmental data, with historical context and clearly stated user requirements. Sources, scientific methods and the team's physics model require team decisions and implementation.

Read the [project brief](docs/project-brief.md), [module responsibilities](docs/architecture.md), [interface planning notes](docs/data-contracts.md) and [contribution workflow](CONTRIBUTING.md). Existing research notes remain reference material, not implemented capabilities.

## Main sections

| Folder under mountain_water/ | Planned scope | Timing |
| --- | --- | --- |
| ui/ | Controls, catchment overview, section views and charts | First phase |
| trend/ | Historical flow, reference periods, seasons, timing, change, variability and comparison | First phase |
| risk_assessment/ | Requirements, exposure, events and user/management context | Later |
| predictionmodel/ | Model inputs, scenarios, comparison baseline, team physics model and evaluation | Much later |

shared/ reserves common contracts, configuration, data access, quality, catchments, coordination, caching and export. Those modules remain placeholders. See the [subsection and file guide](docs/architecture.md) for intended responsibilities and the [trend guide](mountain_water/trend/README.md) for the existing backend.

## Start a teammate branch

```text
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feature/your-task
```

Preserve uncommitted work first. Use a separate worktree when another person or agent is working in your checkout. UI and integration PRs target main. Backend contributors retain their work/backend feature-branch workflow; accepted backend work reaches main through an integration PR.

Use any editor. No repository-prescribed extensions, Dev Container, Supabase account or Vercel account is needed for this Git workflow; teammates need access to the GitHub repository.

With Python 3.11 or later in a virtual environment:

```text
python -m pip install -e ".[dev]"
python -m mountain_water.ui
python -m mountain_water.trend --help
python -m pytest
```

ExecuteProgram.py and streamlit_app.py remain empty; use the module command above. Streamlit is no longer used. See [SETUP.md](SETUP.md), the [UI guide](mountain_water/ui/README.md) and [the trend guide](mountain_water/trend/README.md). The UI's risk, requirements and predictions include imaginary stand-ins; the dedicated risk and physics-model modules remain unfinished.

Earlier generated implementation is preserved on [archive/generated-implementation](https://github.com/saidzeki34/spaceapps-2026-earth-trend-detective/tree/archive/generated-implementation), commit 165e09b. It was never merged into main. It is an archive, not the accepted foundation; do not merge it wholesale.

The team owns subsequent code, methods and data choices. No deployment is included.
