# Working from the combined main branch

Preparation has ended. Main contains the existing UI and trend backend. They run separately; their data connection and the later risk/prediction sections remain unfinished.

## Get a separate working folder

Inspect `git status` first. If another person or assistant is editing your checkout, leave its files and branch alone and create a worktree:

```text
git fetch origin
git worktree add -b feature/your-task ../earth-trend-your-task origin/main
```

Open that new folder in your editor. With a clean, idle checkout you can instead fast-forward main and create a feature branch there. PRs target main. Existing develop and work/* branches are preserved; never reset or force-push them to synchronize.

If you have uncommitted work, save it on your own feature branch after coordinating with the person or assistant using that checkout. Merge origin/main into that branch and resolve conflicts there. A branch name marked with `*` in an editor usually indicates local changes, not a second main branch.

## Python environment and commands

Use Python 3.11 or later and a virtual environment belonging to your checkout. On Windows PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev,ui]"
.venv/Scripts/python.exe -m streamlit run mountain_water/ui/app.py
```

On other systems, activate the environment and use `python -m pip install -e ".[dev,ui]"` and `python -m streamlit run mountain_water/ui/app.py`.

The `ui` extra installs Streamlit. `dev` adds pytest. Backend-only users can install `.[dev]` without the UI extra. The following commands do not download observation datasets:

```text
python -m mountain_water.trend --help
python -m pytest
```

The backend tests use synthetic fixtures and fake API responses. See [the trend guide](mountain_water/trend/README.md) for dataset download/build/report commands and Earthdata authentication. Live service access and scientific interpretation are separate from these checks.

The UI can show empty states and explicitly labelled sample previews without backend data. Map tiles and Leaflet load over the internet; source and geometry limitations are in [the map guide](mountain_water/ui/map_component/README.md). Root ExecuteProgram.py and streamlit_app.py remain empty.

## Local tooling and preserved work

Use any editor; no repository-prescribed extensions, Dev Container, Supabase or Vercel account is needed. Keep credentials and account connections local. Deleting repository configuration does not disconnect externally installed GitHub apps.

The superseded generated implementation remains on archive/generated-implementation at 165e09b and is not part of main. The saved UI was preserved independently on archive/ui-snapshot-20261115 before integration. See [the handoff](docs/team-integration.md). Active local files and unpublished work on teammates' computers must be checkpointed separately; a remote merge cannot collect unsaved editor buffers.
