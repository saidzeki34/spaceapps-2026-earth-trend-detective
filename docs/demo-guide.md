# Demo guide

Install and launch from the repository root using [SETUP.md](../SETUP.md). Use the exact checked commit identified in [validation.md](validation.md). Provider access and scientific interpretation are separate from whether the interface starts successfully.

## Measured Swiss historical example

1. Run `python ExecuteProgram.py` and open the local Streamlit address.
2. Choose **Provider data**, **Switzerland**, and **Chamuerabach · La Punt-Chamues-ch** (station 2263).
3. Use analysis **2011-01-01 through 2020-12-31**, reference years **2001–2010**, **All months** and an **October** water-year start. The incomplete first/last water years illustrate the strict completeness rule.
4. Keep the example **1 m³/s** requirement and identify its intended user. Explain aloud that it is a hypothetical threshold, not verified local demand or an established ecological standard.
5. Leave NASA selected to show its independent access state, or disable it when demonstrating only observed flow. Select **Seasonal baseline** and a clearly stated outlook issue date, then click **Run assessment**.
6. Verify the result names CAMELS-CH v0.9 and shows a retrieval origin/date. The provider downloads the selected historical station member on demand, uses a valid local cache, or reads an explicitly configured local archive. It does not claim present-day Swiss observations.

In **Flow & threshold**, explain rate versus volume, historical band versus requirement, assessed coverage, below-threshold duration, deficit volume and censored runs. In **Timing & variability**, point out missing incomplete periods and the three distinct axes. A ten-year analysis generally cannot meet the twenty-consecutive-year interval requirement; `insufficient_evidence` is an expected, honest result even when a descriptive slope is available.

For an exploratory interval demonstration, choose a longer supported historical window with at least twenty consecutive complete water years. Report the selected window and quality/coverage; do not promise an interval before checking the actual data. Review the statistical assumptions in [methods.md](methods.md).

## NASA and Norway routes

With locally configured Earth Engine authentication and `EARTH_ENGINE_PROJECT`, the NASA tab requests QA-screened MODIS NDSI over the matched upstream catchment. A short window is useful for a first authorized request. Check that provider status is `ready`, valid-area fractions are shown and the index is described as NDSI rather than snow-water or percentage area. Save actual product/version, dates, origin and limitations from the export. If credentials, quotas or data access fail, present that state accurately; do not replace it with a screenshot or synthetic result described as measured data.

For Norway choose **Atnasjø · Atna**, station **2.32.0**, and use an authorized `NVE_API_KEY`. Confirm the returned dates, quality screening and coverage. Historical station existence is not a guarantee that every requested daily record is available. Follow [data-contracts.md](data-contracts.md) for a documented real-data CSV import when direct access is unavailable.

NASA and flow can succeed or fail independently. A working adapter is not evidence that NASA data were actually used in the submitted analysis; retain the successful retrieval/export evidence before making that claim.

## Outlook and export

The next-year panel is a twelve-month historical seasonal baseline. If the issue date is much later than the archive's last observation, explain the stale-history warning. Historical percentile bands are not prediction intervals. Monthly scenario deficit volumes cannot establish daily shortage events.

Selecting **Team equation (awaiting formula)** must show unavailable status. No equation or coefficients have been invented. Finish with **Sources & export** and download the evidence ZIP; check the selected outlet, request, source versions, requirements, coverage and limitations in `evidence.json`.

## Offline developer demonstration

Select **Developer demo (synthetic)** explicitly, retain the displayed warning, disable NASA, and run the default assessment. This exercises the shared calculation/interface path without provider access. The demonstration has a separate identity and no real catchment map. Deliberate missing observations illustrate coverage and incomplete-period handling. Never use this route as environmental evidence, a NASA-use claim or an automatic fallback after a provider error.

## Before presenting

- Check the actual checkout/commit, environment and latest recorded checks.
- Choose a reproducible window and clearly labelled requirement; retain the evidence bundle.
- Read the access states before describing any result as real observations.
- Ask the scientific reviewer to approve claims about trends, drivers and user consequences.
- Avoid exposing credentials while showing settings or terminal output.
- Recheck the team's submission requirements and attribution, including actual AI and NASA use.
