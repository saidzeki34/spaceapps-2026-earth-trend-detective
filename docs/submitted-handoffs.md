# Submitted UI and trend handoffs — 2026-11-15

The user confirmed that Claude's UI and Jonathan's trend work were handed in and requested convergence on main. This supersedes the current-state description in the [earlier integration handoff](team-integration.md), which remains a historical record of PR #9.

## Preserved sources

| Work | Source checkpoint | Treatment |
| --- | --- | --- |
| Claude's submitted local web UI | archive/ui-handoff-20261115 at 01c421a | Saved and pushed before integration, including deliberate removal/replacement of the former Streamlit files |
| Jonathan's submitted backend | work/backend at 46b8933 | Merged with full history, including Norway/seNorge/GLDAS and Swiss/Norwegian station views from PRs #10, #11 and #12 |
| Earlier shared integration | main at e2affdd | Base retained; prior UI and generated-code preservation branches remain available |

No original branches were reset, force-pushed or deleted. The older archive/generated-implementation remains excluded. DFL's previously skipped commercial file is not part of this handoff.

There were no code merge conflicts. AGENTS.md, CLAUDE.md, the decision log and source ledger conflicted; both contributors' records and the backend-specific work/backend workflow were retained. UI/integration work uses main. The handoff's UI source/assets and backend calculations/tests are unchanged. One backend CLI help string was corrected: a literal percent sign made argparse crash on `stations --help`. Configuration removes the unused Streamlit dependency, keeping an empty ui extra for compatibility with the previous install command.

## Run and current boundaries

```text
python -m pip install -e ".[dev]"
python -m mountain_water.ui
python -m mountain_water.trend --help
python -m mountain_water.trend stations --help
```

The UI is a standard-library local server plus HTML/CSS/JavaScript. It reads saved Swiss CAMELS-CH results from data/processed/trend. Without those tables it serves explicitly labelled imaginary records. Its evaporation, requirements, risk scores, predictions and physical-model stand-ins retain the limitations in the [UI guide](../mountain_water/ui/README.md).

The backend supports Norwegian observations, GLDAS comparisons and station views through its CLI. Those additional outputs are not yet consumed by the submitted UI. Dedicated risk assessment, prediction and shared coordination modules remain unfinished. Merging the handoffs does not validate scientific methods or turn imaginary stand-ins into measurements.

## Checks

Validation uses the isolated tmp/submitted-ui-trend checkout, the existing Python environment and the previously isolated missing dependencies in tmp/integration-check-deps. No real observation downloads or live data API requests are made.

- Local HTTP smoke: HTML/CSS/JavaScript/Leaflet/display geometry served; bootstrap and river menus loaded; absent-data fallback worked and remained labelled imaginary.
- Saved synthetic backend output was read through the submitted UI loader and HTTP API. Monthly and daily graphs, usual-year comparison, statistics/risk/model sections and prediction responses serialized successfully. Observed-vs-imaginary flags were checked, including imaginary evaporation and predictions.
- Unknown routes and river IDs returned 404. The temporary HTTP server was closed after the checks.
- UI command help and corrected station command help succeeded. All four authored JavaScript modules passed node syntax checks.
- The existing backend suite is run separately; its final result and GitHub merge status are recorded in the integration PR.

These are software checks with synthetic fixtures. Browser rendering, satellite tiles, live service access, scientific claims and source licence review are outside their coverage. No deployment or repository service/editor integration is added.
