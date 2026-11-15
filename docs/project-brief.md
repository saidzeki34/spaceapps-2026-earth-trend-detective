# Project context

The Oslo team is participating in NASA Space Apps 2026, Earth System Trend Detective. Preparation has ended. The user corrected the previous handoff: this delivery establishes documentation and an empty shared structure, while teammates write the implementation.

## Intended investigation
Explore mountain-catchment water availability in Norway and Switzerland. The intended inputs are measured river observations, catchment context, relevant NASA environmental observations and separately documented user requirements. Potential outputs include historical context, changes over time, requirement exposure and an outlook from the team's physics model.

These are project intentions, not available features. No station catalogue, data integration, scientific method, interface design, model equation or result is implemented or endorsed by this skeleton. The team must confirm sources, spatial/temporal coverage, units, licences, quality information and scientific interpretation.

The planned code organization is one Python application with Streamlit entry points and shared modules. Empty files reserve responsibilities without selecting algorithms or dependency versions. The physics model remains a team-owned task; no formula is supplied here.

The team's sections are ui and trend for the first phase, risk_assessment later, and predictionmodel much later. Common source access, configuration and input/output concepts are grouped under shared. The subsection responsibilities and empty file map are in [architecture.md](architecture.md).

## Delivery boundary
Included: this context, module responsibilities, interface discussion topics, active-phase instructions and zero-byte placeholders.

Excluded: executable code, algorithms, integrations, UI, models, database schemas, data downloads, application tests and deployment.

Existing challenge references and research notes retain their original verification limits. A separate archive branch preserves previously generated work without making it part of the accepted foundation.
