# Team sections and phases

The shared delivery remains documentation and empty placeholders. The latest reorganization groups the skeleton into the team's four sections; it does not implement them.

| Section | Planned timing | Subsections | Human owner |
| --- | --- | --- | --- |
| ui | First phase | Controls, navigation/state, catchment overview, trend display, charts | Team to assign |
| trend | First phase | Preparation, flow summaries, reference history, seasons, timing, change, variability, comparison | Team to assign |
| risk_assessment | Later | Requirements, exposure, events, user/management context | Team to assign |
| predictionmodel | Much later | Interface, inputs, scenarios, baseline, physics model, calibration, prediction, evaluation | Team to assign |
| shared | Supports the sections as needed | Contracts, configuration, source access, quality, catchments, coordination, cache, export | Coordinate across owners |

## Next team decisions

- [ ] Assign one human owner and a small task before filling any placeholder.
- [ ] Agree the first ui/trend input and output concepts in shared/contracts.py.
- [ ] Confirm source access, units, coverage, licensing and quality information for the first historical investigation.
- [ ] Agree the historical questions, reference period and scientific methods before implementing trend calculations.
- [ ] Keep later UI sections and model functionality unavailable until separately implemented.
- [ ] Define sourced requirements and interpretation before starting risk assessment.
- [ ] Supply the team's physics equation, parameters and future-driver assumptions before starting predictionmodel.
- [ ] Add dependency choices, run commands and appropriate checks with the future implementation PRs.

The earlier generated application remains archived at archive/generated-implementation, commit 165e09b. It is not part of the accepted skeleton. No implementation, model validation or live-provider success is claimed here.
