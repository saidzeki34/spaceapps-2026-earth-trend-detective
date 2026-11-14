# Planned structure and responsibilities

Every source file listed here is an empty placeholder. This is an ownership map for teammate work, not a runnable architecture.

```text
ExecuteProgram.py
streamlit_app.py
mountain_water/
  __init__.py
  config.py
  contracts.py
  data/
    __init__.py
    base.py
    nve.py
    swiss.py
    nasa.py
    csv_import.py
    quality.py
  analysis/
    __init__.py
    flow_metrics.py
    baseline.py
    risk.py
    trends.py
    variability.py
  models/
    __init__.py
    base.py
    climatology.py
    team_model.py
    validation.py
  services/
    __init__.py
    assessment.py
    cache.py
    export.py
  visualization/
    __init__.py
    maps.py
    timeseries.py
    risk.py
    variability.py
  ui/
    __init__.py
    app.py
config/
  catchments/
data/
scripts/
tests/
docs/
```

Empty directories are tracked with empty .gitkeep files. Existing repository administration files are retained.

| Area | Planned responsibility | Boundary |
| --- | --- | --- |
| Entry points | Launcher and application entry | Delegate behavior to modules |
| contracts.py | Shared input/output definitions | Team agreement before callers/providers are built |
| config.py and config/ | Project configuration and reviewed catalogues | Keep credentials local |
| data/ | Source access, imports, quality and provenance | Return documented data/access states; no fabricated fallback |
| analysis/ | Historical flow, reference context, requirements, change and variability | Methods and assumptions require scientific review |
| models/ | Common model interface, comparison baseline, team physics model and evaluation | No equation or implementation supplied |
| services/ | Coordinate an assessment, cache policy and evidence handoff | Keep computation/source logic in their modules |
| visualization/ | Present supplied results and their limitations | Do not silently compute or reinterpret science |
| ui/ | Future user interaction | Teammate implementation; no screen design included |
| data/, scripts/, tests/ at root | Future local data, utilities and checks | Empty; no observations, utilities or tests delivered |

One human should own each task. Agree shared-file changes first and use separate worktrees for concurrent writers. Specific assignments remain with the team.
