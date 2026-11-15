# Interface planning notes

mountain_water/shared/contracts.py is empty. These concepts are for teammates to agree before implementing them; they are not dataclasses, schemas or executable contracts.

| Concept | Questions to resolve together | Sections using it |
| --- | --- | --- |
| Outlet | Stable identity, source station, upstream catchment and management context | shared, ui, trend; later sections as needed |
| Provenance | Provider/product/version, attribution/licence, retrieval time and transformations | All sections |
| FlowSeries | Units, interval meaning, timestamps, missing values and retained quality information | shared, trend; later risk and prediction |
| DriverSeries | Environmental variable, spatial/temporal support, aggregation and valid coverage | shared, trend; later prediction |
| AssessmentRequest | Selected location, dates, reference period and requested section | ui, shared and the selected section |
| TrendResult | Historical summaries, change/timing/variability outputs, coverage and scientific limitations | trend to ui through shared coordination |
| RequirementSeries | Intended user, units, source, scenario/documented need and applicability | Later risk assessment |
| RiskAssessmentResult | Requirement exposure, event information and limits on interpretation | Later risk assessment to ui |
| ForecastResult | Model identity, issue date, target intervals, scenario assumptions and evaluation context | Much later predictionmodel to ui |

The section result concepts refine the earlier umbrella AssessmentResult discussion. The team must decide concrete fields and whether a common result wrapper is useful; no compatibility API exists yet.

Agree how shared source access reports ready, authentication-required, pending, unsupported, no-data and error states. Preserve missing observations separately from zero. Distinguish observations, hypothetical requirements, future scenarios, model outputs and any explicitly labelled synthetic development material.

ui presents inputs and supplied outputs. trend owns historical analysis. risk_assessment owns later requirement interpretation. predictionmodel owns much later predictions. shared coordinates them without requiring deferred sections during initial development.

No validation rules, algorithms or field-level schema are supplied. Record interface decisions in decision-log.md before implementing shared records.
