# Local development

Python **3.11** is tested. constraints.txt records resolved versions; pyproject.toml declares dependencies.

## Windows PowerShell
```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -c constraints.txt -e ".[dev]"
.venv\Scripts\python.exe ExecuteProgram.py
```

If py is absent, use your installed Python 3.11 executable to create the environment. Activation is optional; explicit paths avoid changing execution policy.

## macOS / Linux
```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -c constraints.txt -e ".[dev]"
.venv/bin/python ExecuteProgram.py
```

Arguments are forwarded to Streamlit, e.g. --server.port 8502. Alternatively run python -m streamlit run streamlit_app.py. Stop with Ctrl+C.

## Editor and checks
Select the virtual environment in VS Code; tracked tasks use that interpreter. The optional devcontainer uses Python 3.11; container execution was not tested here.

```text
python -m ruff check .
python -m pytest
```

If system temp is inaccessible, use a new disposable directory inside the checkout: python -m pytest --basetemp=tmp/check-1. Pytest may erase an existing basetemp directory; never point it at source files.

## Provider access
Copy .env.example to .env locally. Never commit it or credentials.

- Switzerland needs no key for the pinned archive. Bounded HTTP byte ranges read the station's observed ZIP member and verify its CRC. If range access is blocked, extract the official archive and set CAMELS_CH_DIR to its root. Coverage is historical 1981–2020. The archive's timezone is unresolved; labels use nominal 24-hour UTC intervals.
- Norway requires your own NVE HydAPI key in NVE_API_KEY. Missing credentials return authentication_required. Daily means use fixed Norwegian standard-day intervals.
- NASA requires EARTH_ENGINE_PROJECT with enabled/registered Earth Engine access, then earthengine authenticate using this environment. Credentials remain in the provider's local store. The app does not create projects or enable billing. Missing access, quotas and processing failures stay visible.

Caches live in ignored data/cache or WATER_CACHE_DIR and retain provenance. Keys and exports contain no credentials. For an explicit network check:

```text
python -m scripts.check_live
```

Reports go to ignored data/exports. Live checks are outside CI; unavailable routes are not reported as successful.

## Imports and catalogue
Flow/driver CSVs require separate provenance JSON and the selected outlet ID. See docs/data-contracts.md and examples/ for labelled format examples. Blanks remain missing.

Verified catalogue metadata and polygons are checked in. To deliberately rebuild from providers:

```text
python -m pip install -c constraints.txt -e ".[dev,catalogue]"
python -m scripts.build_catalogue
```

This optional network task downloads into ignored data/raw. Review source changes and geometries before committing.

## Branches
```text
git fetch origin
git switch main
git pull --ff-only
git switch -c feature/your-small-task
```

Preserve uncommitted work. Use separate worktrees for simultaneous writers. Open PRs to main after checks; preserve develop and work/* branches. Setup does not authorize deployment.
