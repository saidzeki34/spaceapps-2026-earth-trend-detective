# Interface planning notes

mountain_water/contracts.py is empty. The names below identify shared concepts for teammates to agree before implementing them; they are not dataclasses, schemas or executable contracts.

| Concept | Questions to resolve together |
| --- | --- |
| Outlet | Stable identity, source station, upstream catchment and management context |
| Provenance | Provider/product/version, attribution/licence, retrieval time and transformations |
| FlowSeries | Units, interval meaning, timestamps, missing values and retained quality information |
| DriverSeries | Environmental variable, spatial/temporal support, aggregation and valid coverage |
| RequirementSeries | Intended user, units, source, scenario versus documented need and applicability |
| AssessmentRequest | Location, analysis dates, separate reference period and chosen requirement |
| AssessmentResult | Evidence, summary outputs, coverage, limitations and source/access states |
| ForecastResult | Model identity, issue date, target intervals, assumptions and evaluation context |

Agree how modules report ready, authentication-required, pending, unsupported, no-data and error states. Preserve missing observations separately from zero. Distinguish measured data, scenarios, model outputs and any explicitly labelled synthetic development material.

No validation rules, algorithms, field-level schema or implementation are supplied. Capture team decisions in decision-log.md before changing shared interfaces.
