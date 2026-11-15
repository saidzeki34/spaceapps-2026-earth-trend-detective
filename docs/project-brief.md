# Project context

The Oslo team is participating in NASA Space Apps 2026, Earth System Trend Detective. Preparation has ended. The initial delivery established documentation and an empty shared structure. The user has now requested integration of the team's existing work; see [team-integration.md](team-integration.md) for the delivered modules and unfinished connections.

## Intended investigation
Explore mountain-catchment water availability in Norway and Switzerland. The intended inputs are measured river observations, catchment context, relevant NASA environmental observations and separately documented user requirements. Potential outputs include historical context, changes over time, requirement exposure and an outlook from the team's physics model.

These are overall project intentions. The UI and the Swiss CAMELS-CH/GLDAS trend backend are now present, but are not connected to one another. Norway's observation integration, requirement assessment and the physics model remain unfinished. The team must review sources, spatial/temporal coverage, units, licences, quality information and scientific interpretation.

The code organization is one Python package with a Streamlit UI and a trend command-line interface. Remaining empty files reserve future responsibilities. The physics model remains a team-owned task; no formula is supplied here.

The team's sections are ui and trend for the first phase, risk_assessment later, and predictionmodel much later. Common source access, configuration and input/output concepts are grouped under shared. The subsection responsibilities and empty file map are in [architecture.md](architecture.md).

## Delivery boundary
The initial skeleton included this context, module responsibilities, interface discussion topics, active-phase instructions and zero-byte placeholders. The subsequent integration brings existing teammate code onto main without completing new features.

The integration does not add new scientific methods, connect the UI to the backend, finish deferred sections, download solution data or deploy.

Existing challenge references and research notes retain their original verification limits. A separate archive branch preserves previously generated work without making it part of the accepted foundation.
