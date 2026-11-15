# Screening UI update — 2026-11-15

Perplexity-assisted implementation requested by the user. No new runtime dependency.
Metric cards now use plain language. The occupation selectors synchronize; changing
occupation clears the threshold. Physical river indicators are occupation-independent.
Five profiles provide conditional planning context, not regional forecasts.

screening-v1: stable below all of |X|=5, |Y|=3, Z=15; changing at any boundary;
strong change/high variability at |X|=10, |Y|=7 or Z=30. Missing XYZ is unavailable.
These are arbitrary prototype screening limits, not calibrated safety thresholds.
No operational verdict without a threshold. Any shortfall flags potential exposure;
zero shortfalls with <90% daily coverage remain undetermined. Otherwise report no
historical shortfall detected, never safe-to-operate approval.

A separate real surface/heatmap uses window ending year, window length (5–15 years)
and normalized seasonal-volume standard deviation. It requires consecutive complete
seasons, leaves gaps blank and includes long-term change. Overlapping windows are
not independent. These axes differ deliberately from the retained XYZ scatter.

Node syntax and rule/surface/profile assertions passed in an isolated sandbox.
Browser interaction and real data remain untested. Python tests were not rerun.
After approval/commit, stop the old server and run on the clean risk branch:

```sh
git pull --ff-only origin risk-assessment/risk-assessment-implementation
python -m pytest tests/risk_assessment -q
node --experimental-default-type=module tests/risk_assessment/risk-rules.test.mjs
python -m mountain_water.ui --no-window --port 8765
```

Node is optional for development tests. Hard-refresh the forwarded browser port.
Check both occupation selectors, threshold clearing, surface/heatmap, XYZ and export.
General sector context: DOE Microhydropower Handbook (flow/head) and FEMP Cooling
Water Efficiency Opportunities for Federal Data Centers (cooling-dependent demand).
Government/defence text is a planning checklist. Team review and attribution required.
