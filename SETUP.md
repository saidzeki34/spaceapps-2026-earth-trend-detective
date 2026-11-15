# Working from the combined main branch

Preparation has ended. Main combines the trend backend with a local web interface for saved results. Swiss/Norwegian observations, GLDAS model comparisons and station heatmaps are available when their corresponding outputs have been built. Risk assessment and prediction remain unimplemented.

## Get a separate working folder

Inspect `git status` first. If another person or assistant is editing your checkout, leave its files and branch alone and create a worktree:

```text
git fetch origin
git worktree add -b feature/your-task ../earth-trend-your-task origin/main
```

Open that new folder in your editor. With a clean, idle checkout you can instead fast-forward main and create a feature branch there. UI and integration PRs target main. Backend feature branches instead start from origin/work/backend and target work/backend, following the backend team's documented workflow; accepted backend work is then integrated onto main. Existing branches are preserved; never reset or force-push them to synchronize.

If you have uncommitted work, save it on your own feature branch after coordinating with the person or assistant using that checkout. Merge origin/main into that branch and resolve conflicts there. A branch name marked with `*` in an editor usually indicates local changes, not a second main branch.

## Python environment and commands

Use Python 3.11 or later and a virtual environment belonging to your checkout. On Windows PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m mountain_water.ui
```

On other systems, activate the environment and use `python -m pip install -e ".[dev]"` and `python -m mountain_water.ui`. The app opens a local window; use `--no-window` to start only the local server and print its address. See the UI README for options and the Windows launcher.

The web server uses the Python standard library and the base project dependencies for data. No Streamlit installation or frontend build is needed. `dev` adds pytest; the old `ui` extra remains empty for command compatibility. The following commands do not download observation datasets:

```text
python -m mountain_water.trend --help
python -m pytest
```

The backend tests use synthetic fixtures and fake API responses. See [the trend guide](mountain_water/trend/README.md) for dataset download/build/report commands and Earthdata authentication. Live service access and scientific interpretation are separate from these checks.

The UI reads saved outputs under data/processed: trend (Swiss), trend_no (Norway), trend_gldas / trend_no_gldas (GLDAS), and trend_stations (station network). The source menu reports what actually exists, including build commands for missing outputs. Nothing downloads on page load. After running a backend build, click **Reload saved results**. See [the trend guide](mountain_water/trend/README.md) for credentials and build details; credentials never belong in Git.

Plotly and Leaflet are served locally; there is no frontend build. Background map tiles require internet, but saved figures, tables, gauge points and cached river geometry work without them. River courses use actual OSM segments where a conservative match is available; unmatched gauges remain points. See [the map guide](mountain_water/ui/map_component/README.md). Root ExecuteProgram.py and streamlit_app.py remain empty.

Focused UI checks (synthetic test fixtures, no downloads):

```text
python -m pytest tests/test_ui_backend.py tests/test_ui_server.py tests/test_ui_river_geometry.py
```


## Local tooling and preserved work

Use any editor; no repository-prescribed extensions, Dev Container, Supabase or Vercel account is needed. Keep credentials and account connections local. Deleting repository configuration does not disconnect externally installed GitHub apps.

The superseded generated implementation remains on archive/generated-implementation at 165e09b and is not part of main. The earlier UI checkpoint is on archive/ui-snapshot-20261115; the submitted web UI is on archive/ui-handoff-20261115 at 01c421a. See [the latest handoff](docs/submitted-handoffs.md). Active local files and unpublished work on teammates' computers must be checkpointed separately; a remote merge cannot collect unsaved editor buffers.
