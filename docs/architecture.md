# Sections and module responsibilities

The application is organized around the team's four sections: **ui**, **trend**, **risk_assessment** (later), and **predictionmodel** (much later). The folder spelling risk_assessment corrects the typo in the discussion. A fifth, supporting shared folder holds common inputs, source access and coordination.

All Python files remain zero-byte placeholders. The tables describe future responsibilities, not implemented features, algorithms or selected scientific methods.

## Folder overview

```text
ExecuteProgram.py
streamlit_app.py
mountain_water/
  __init__.py
  ui/
    charts/
  trend/
  risk_assessment/       # later
  predictionmodel/       # much later
  shared/
    data/
config/
  catchments/
data/
scripts/
tests/
docs/
```

Each Python package also has an empty __init__.py. Root data/, scripts/ and tests/ retain empty tracking placeholders. Entry points remain empty.

## ui — first phase

Owns selection, navigation and presentation. It receives results through shared coordination; scientific calculations belong to their section.

| Subsection | Placeholder files | Future responsibility |
| --- | --- | --- |
| Application and navigation | app.py | Assemble the Streamlit sections; keep later sections unavailable until implemented |
| Assessment controls | controls.py | Country/catchment, dates, variable, reference period and other agreed selections |
| Session state | state.py | Retain selections and distinguish current results from changed inputs |
| Catchment overview | overview.py | Present outlet context, source information, coverage and access state |
| Trend screen | trend_view.py | Present historical evidence and results supplied by trend |
| Later screens | risk_view.py, prediction_view.py | Reserve future requirement-exposure and model views; no UI implementation now |
| Maps and historical charts | charts/maps.py, charts/timeseries.py, charts/variability.py | Render catchments, supplied time series, comparisons and variability |
| Later charts | charts/risk.py, charts/prediction.py | Present future exposure and forecast outputs with their limitations |

## trend — first phase

Owns investigation of historical observations. NASA environmental observations can provide context when the team establishes suitable data; no product or statistical method is chosen by these filenames.

| Subsection | Placeholder file | Future responsibility |
| --- | --- | --- |
| Analysis preparation | preprocessing.py | Prepare selected records for analysis while retaining units, interval meaning and missingness; source quality handling stays shared |
| Flow and volume summaries | flow_metrics.py | Summarize historical discharge and volume using a team-reviewed method |
| Reference history | baseline.py | Describe a separately selected historical reference period |
| Seasonal patterns | seasonal.py | Organize seasonal/year summaries and document completeness |
| Flow timing | timing.py | Investigate when water arrives within a season/year; timing definition requires team agreement |
| Change over time | trends.py | Estimate and communicate historical change, with reviewed uncertainty and dependence assumptions |
| Variability | variability.py | Describe fluctuations separately from the long-term change |
| Catchment comparison | comparison.py | Compare compatible periods, units and coverage between selected catchments |

Reference history is distinct from a user's requirement and from a future prediction. Historical association does not establish cause.

## risk_assessment — later

Owns the interpretation of water availability against a documented requirement. It consumes shared observations or reviewed trend outputs; it does not fetch a separate copy of the data.

| Subsection | Placeholder file | Future responsibility |
| --- | --- | --- |
| Requirement definition | requirements.py | Describe the intended user, requirement source, units, temporal support and scenario/documented status |
| Exposure | exposure.py | Assess availability against the requirement after methods and interval compatibility are agreed |
| Shortfall events | events.py | Describe event duration and frequency with explicit treatment of missing periods |
| User and catchment context | context.py | Record management, resilience and other limits on interpreting exposure as risk |

A threshold crossing alone must not be presented as operational failure or a universal risk score. UI files for this section are under ui/; calculations and interpretation belong here.

## predictionmodel — much later

Owns the team's future outlook and physics model. It remains unavailable until the team supplies the equation, parameters, assumptions and evaluation plan.

| Subsection | Placeholder file | Future responsibility |
| --- | --- | --- |
| Model interface | base.py | Agree common model inputs and outputs with shared/contracts.py |
| Input preparation | inputs.py | Assemble the model's required history and environmental drivers |
| Future assumptions | scenarios.py | Describe future drivers and operating assumptions; distinguish scenarios from measurements |
| Comparison baseline | climatology.py | Reserve a simple seasonal comparison model, with method and suitability to be reviewed |
| Team physics model | team_model.py | Hold the team's equation and implementation when explicitly supplied |
| Parameter calibration | calibration.py | Estimate or document model parameters using an agreed training period |
| Prediction coordination | predict.py | Coordinate a chosen model and scenario for the requested horizon |
| Evaluation | validation.py | Evaluate chronological held-out predictions and compare against the baseline without future-data leakage |

The historical reference in trend/baseline.py and the model comparison in predictionmodel/climatology.py have different responsibilities. File names do not authorize model implementation during this skeleton task.

## shared — supporting all sections

| Subsection | Placeholder files | Future responsibility |
| --- | --- | --- |
| Shared records | contracts.py | Agree common input/output concepts, provenance and access states |
| Configuration | config.py | Read reviewed project settings; keep secrets local |
| Assessment coordination | assessment.py | Connect source access and the requested section; first-phase work must not require later modules to be implemented |
| Caching | cache.py | Reuse documented inputs with source/version and relevant request identity |
| Evidence handoff | export.py | Package supplied results, sources and limitations |
| Source interfaces | data/base.py | Define provider boundaries and honest availability states |
| Candidate source adapters | data/nve.py, data/swiss.py, data/nasa.py | Reserve Norwegian, Swiss and NASA access responsibilities; access and products remain unverified here |
| Explicit imports | data/csv_import.py | Import documented user-provided observations |
| Source quality | data/quality.py | Retain provider flags, units and missing-value meaning |
| Catchment context | data/catchments.py | Connect outlet metadata and verified upstream boundaries |

config/catchments/ is reserved for future reviewed configuration/boundaries. Root data/ is for local data, while shared/data/ is for future access code. No observations or boundaries are added by this reorganization.

## Where existing placeholders moved

| Previous location | Current location |
| --- | --- |
| analysis/ historical files | trend/ |
| analysis/risk.py | risk_assessment/exposure.py |
| models/ | predictionmodel/ |
| visualization/ | ui/charts/ |
| data/ inside mountain_water | shared/data/ |
| services/ files | shared/ |
| mountain_water/contracts.py and config.py | shared/contracts.py and shared/config.py |
| ui/app.py | Kept in place |

Keep one agreed human owner per task. Coordinate shared interfaces and use separate worktrees for simultaneous writers. No ownership assignment is implied by this layout.
