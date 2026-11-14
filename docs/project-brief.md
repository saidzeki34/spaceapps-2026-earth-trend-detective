# Mountain Water Availability

The team is implementing the selected **Codex_Project_Handoff (3).pdf** as one Python application for the Earth System Trend Detective challenge. Competition work was explicitly authorized on 2026-11-15. Earlier preparation records remain historical context; earlier handoff versions are not the implementation specification.

## Question and audience

For a measured mountain-river outlet, how have water quantity, seasonal timing and year-to-year variability changed, and how does observed flow compare with a clearly identified requirement?

The application supports investigation by river-ecosystem, municipal, irrigation, hydropower and other water-dependent users. It reports river-flow threshold exposure. It does not turn that exposure into a universal risk score, delivered water supply or a claim of service failure: storage, abstraction, routing, operations and user resilience are generally unknown.

## Implemented foundation

- One Streamlit interface launched by `python ExecuteProgram.py`, with shared contracts and separate provider, analysis, model, service and visualization modules.
- Two measured outlets with provider-matched upstream polygons: Norway's NVE **2.32.0, Atnasjø / Atna**, and Switzerland's FOEN **2263, Chamuerabach / La Punt-Chamues-ch** through CAMELS-CH v0.9.
- On-demand observed discharge, explicit imports and scientific cache identities. An unavailable provider never triggers substitute observations.
- A historical calendar-day baseline kept separate from analysis dates and the user's requirement; complete seasonal volumes; half-annual-volume timing; three quantity, timing and variability axes.
- Native-interval threshold comparison with duration weighting, coverage and censored event boundaries.
- NASA MODIS v061 catchment NDSI context with quality screening and valid-area reporting, subject to authorized Earth Engine access or a documented import.
- A twelve-month seasonal-climatology outlook with chronological hindcasts. The team's physical equation remains unavailable until supplied and validated.
- Evidence export containing inputs, results, provenance, coverage, assumptions and limitations.

## Access and interpretation boundaries

The Swiss route is a **1981–2020 historical archive**, not a current FOEN feed. Norwegian HydAPI requires an API key and checks availability for the requested dates. NASA retrieval requires an authorized Earth Engine project and local authentication. These independent states are shown in the interface; successful flow retrieval does not imply successful NASA retrieval. See [validation.md](validation.md) for checks actually performed and access still unverified.

The default **1 m³/s requirement is an adjustable hypothetical scenario**. It is neither measured demand nor a scientifically established environmental-flow standard. A documented requirement must retain its source, intended user, units, applicability and resilience assumptions.

The NASA variable is an area-weighted mean **NDSI index**, not snow-water volume or percentage snow-covered area. Historical observations can reflect management and measurement limitations. Associations and descriptive trends do not establish cause.

An explicitly selected developer demonstration contains synthetic data, has its own outlet identity and is labelled throughout. Its purpose is interface and calculation demonstration, not environmental evidence or a provider fallback.

## Completion and next work

The foundation must be runnable from the shared `main` branch through the reviewed contribution workflow, with reproducible dependencies, offline checks, a documented real-data check and a traceable commit. No hosting service or database is required for local use. Credentials, model equations, scientific review and submission decisions remain explicit team responsibilities; see [task-checklist.md](task-checklist.md).

Read [architecture.md](architecture.md), [data-contracts.md](data-contracts.md), [methods.md](methods.md), [source-ledger.md](source-ledger.md) and [demo-guide.md](demo-guide.md) before extending or presenting results.
