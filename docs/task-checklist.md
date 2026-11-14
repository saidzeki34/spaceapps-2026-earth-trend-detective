# Team task checklist

This is the active competition handoff for the implementation of **Codex_Project_Handoff (3).pdf**. It is not a preparation gate. A checked implementation item means code or documentation exists; successful checks, provider access and scientific acceptance must be supported separately by [validation.md](validation.md), [source-ledger.md](source-ledger.md) and review records.

## Foundation implemented

- [x] One launch command, one Streamlit app, shared interval/provenance contracts and modular services.
- [x] Verified catalogue joins for Norwegian 2.32.0 and Swiss 2263 outlets and upstream geometries.
- [x] NVE, historical CAMELS-CH, NASA MODIS and explicit import adapters with visible access states.
- [x] Interval volume, separate reference baseline, completeness rules and half-volume timing.
- [x] Requirement coverage, deficit/margin volume, equality policy and censored observed runs.
- [x] Distinct quantity, timing and residual-variability axes with 3D and 2D presentation.
- [x] Seasonal monthly baseline, chronological hindcasts and an honest unavailable team-model extension.
- [x] Evidence export and explicitly labelled opt-in synthetic developer demonstration.
- [x] Numerical, provider, service and interface test cases are present; presence is not a passing-test claim.

## Integration acceptance

- [ ] Record the exact tested commit and reproducible dependency/environment versions.
- [ ] Record offline test, lint, import and local launch outcomes.
- [ ] Record a real Swiss archive assessment, source retrieval date, observed coverage and export inspection.
- [ ] Document precise NASA/NVE access outcomes; distinguish live checks from mocked adapter tests.
- [ ] Review changes to shared contracts and scientific assumptions.
- [ ] Merge the foundation PR to `main` when required checks/reviews are satisfied; record PR and merge SHA.
- [ ] Tag the tested demo commit and share launch instructions with teammates.

The integrator updates these acceptance boxes only after evidence exists. An access-blocked optional provider remains visibly blocked; it does not justify claiming all routes succeeded or replacing observations.

## Six workstreams and next deliverables

| Workstream | Next concrete deliverable | Human owner |
| --- | --- | --- |
| Data and provenance | Verify authorized live NVE and NASA runs, quality policy and exact retrieved metadata; expand catalogue only with verified joins | Assign in team roster |
| Historical hydrology | Review calendar choices, season/year completeness, baseline windows and half-volume interpretation on measured records | Assign in team roster |
| Requirements and exposure | Supply sourced user-specific requirements and applicability/resilience information; review finer-than-flow requirement handling | Assign in team roster |
| Models and validation | Supply the team equation and parameters, future-driver assumptions and leakage-free comparison against climatology | Assign in team roster |
| Visualization and interface | Review readable labels, keyboard/accessibility behavior, empty/error states and measured-data demo narrative | Assign in team roster |
| Integration, quality and delivery | Own PR checks, source ledger, tested commit/tag, team handoff and submission completeness | Assign in team roster |

Do not infer ownership from a reserved `work/*` branch. Record one human owner for each task and coordinate shared files through the contribution workflow.

## Scientific and submission review still required

- [ ] Review station-to-catchment correspondence, coordinates, source license and management context.
- [ ] Review NVE controlled-data filtering, Swiss missing quality flags/ice limitations and nominal date interpretation.
- [ ] Review MODIS flags, changing valid-area bias and the project-specific 50% coverage rule.
- [ ] Review exploratory block-bootstrap assumptions, short records, repeated searches and fixed-baseline normalization.
- [ ] Avoid interpreting measured trends as causal explanations or scenario thresholds as documented needs.
- [ ] Supply and validate the team's model before enabling it as an available forecasting method.
- [ ] Establish actual NASA data use required for the submission; provider code alone is insufficient evidence.
- [ ] Confirm current official challenge resources, Local Event requirements, deadline, registrations and final scientific/media claims.
- [ ] Retain software/data/AI attribution and complete [submission-checklist.md](submission-checklist.md).

Every task handoff should name changed files, exact checks and outcomes, data/provenance effects and remaining questions. Do not commit secrets, downloaded raw archives, local caches or account configuration.
