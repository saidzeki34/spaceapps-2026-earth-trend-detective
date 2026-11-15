# Project context

The Oslo team is participating in NASA Space Apps 2026, Earth System Trend Detective. Preparation has ended. The initial delivery established documentation and an empty shared structure. The submitted work has been integrated. The current task retains Claude's original interface while connecting the team's saved trend results; see [ui-restoration.md](ui-restoration.md).

## Intended investigation
Explore mountain-catchment water availability in Norway and Switzerland. The intended inputs are measured river observations, catchment context, relevant NASA environmental observations and separately documented user requirements. Potential outputs include historical context, changes over time, requirement exposure and an outlook from the team's physics model.

These are overall project intentions. The web UI reads saved Swiss CAMELS-CH and Norwegian NVE/seNorge results, GLDAS comparisons and station views through the trend backend. Missing local builds remain unavailable. Requirement assessment and the physics model remain unfinished; no fabricated observations or operational scores substitute for them. A separate labelled 3D surface is a visual demonstration only. The team must review sources, spatial/temporal coverage, units, licences, quality information and scientific interpretation.

The code organization is one Python package with a local web UI and a trend command-line interface. Remaining empty files reserve future responsibilities. The physics model remains a team-owned task; no formula is supplied here.

The team's sections are ui and trend for the first phase, risk_assessment later, and predictionmodel much later. Common source access, configuration and input/output concepts are grouped under shared. The subsection responsibilities and empty file map are in [architecture.md](architecture.md).

## Delivery boundary
The initial skeleton included this context, module responsibilities, interface discussion topics, active-phase instructions and zero-byte placeholders. The subsequent integration preserved teammate code, followed by the explicitly requested UI data integration. The current restoration changes the UI back to Claude's appearance while retaining those data connections.

The current task does not add scientific methods, finish deferred sections, download observation data or deploy.

Existing challenge references and research notes retain their original verification limits. A separate archive branch preserves previously generated work without making it part of the accepted foundation.
