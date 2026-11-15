# UI mechanical fixes and accepted risk submission — 2026-11-15

The user requested a continuation of Claude's selected UI with mechanical fixes only, and explicitly accepted Nikola's risk-assessment branch. The existing typography, colours, layout, occupation selector and real-data workflow are retained. This instruction supersedes the earlier wait for risk-branch readiness recorded in selective-unification.md.

## Branches and preservation

- Integration starts from main at `0e7823df73774bb7429d8f256cf4317225f32ae1` in the separate `integration/ui-mechanics-risk-20261115` worktree.
- Nikola's `risk-assessment/risk-assessment-implementation` at `8c168c81e63793e757d1f7b1c59524b7fcacf36e` is merged with its original history. The existing UI adapter conflict is resolved without removing the current trend headline.
- `ui-fixes-continuation` at `7d25d5d2a55371eb83d7eac16df1cd6d4effb32b` is explicitly excluded. Its generated UI chunks and workflow are not imported.
- Jonathan's accepted `work/backend` at `46b8933` and Claude's accepted UI are already ancestors of main. No other outstanding submitted branch was found at initial inspection.
- All source branches and archives remain intact. The selected UI is also preserved at `4a708b4` on `archive/local-ui-before-unification-20261115`. The generated-application archive and historical backup are not submissions and remain separate. No force push or history rewrite is used.

## Changes and limits

Graph **Rescale** fits all axes to their original data and units; it does not compare unlike variables by silently normalizing them. Results **Close** and map **Results** preserve the river/year selection. The existing controls and visual styles are reused. Late table/CSV responses for an earlier selection are discarded so the table cannot silently show a different year from the graph.

River geometry uses source vertices and conservative gauge matching. Coverage increased from 22 to 77 of 117 gauges (23 in the Swiss selection, 54 in Norway), retaining all prior matches. Both Lütschine branches are now represented. Connections and branches are shown only when supported by the cached source network; gaps are not bridged with invented lines. Forty gauges remain unavailable and source/mouth endpoints are not verified. Administrative/reference boundaries remain subtle. Exact coverage and provenance are recorded in the [map guide](../mountain_water/ui/map_component/README.md).

Nikola's historical assessment reads the saved observed daily discharge and excludes flagged interpolation. It provides descriptive flow indicators, historical variability and optional constant-threshold exposure. The adapter rejects GLDAS/model inputs. Prototype screening thresholds are arbitrary and explicitly unvalidated; neither the merge nor software tests constitute scientific approval or an operational safety determination. The physics/prediction model remains unfinished.

Observation downloads, processed data, credentials and local browser artifacts remain outside commits. Opening the interface does not fetch observations or build trend results.

## Validation

Completed software checks in the isolated checkout:

- **71 Python tests passed:** 57 UI backend/server and risk tests (66.57 seconds), plus the final 14 geometry tests (0.29 seconds). Pytest plugin autoload was disabled and temporary artifacts were kept under ignored tmp/. The unchanged full trend suite was not rerun.
- Node screening assertions, JavaScript module syntax and git diff --check passed. No trend or prediction source changed; risk_assessment/assessment.py matches Nikola's submitted commit exactly. No excluded .chunks or workflow files were imported.
- Browser checks covered two/three/four variables, rescaling all Cartesian axes with unchanged values, explicit 3D range and camera reset with byte-identical surface data, normal/expanded results close/reopen, a delayed table response after a year change, correct CSV year, and 420 px controls without page overflow. Before/after screenshots were inspected against the preserved interface.
- The assessment opened from the current UI with real saved observations. GLDAS input produced the expected HTTP 400 and a visible explanation. Rapid recalculation, immediate close/reopen, 2D/3D toggles and occupation changes during rendering were exercised. The resulting fixes serialize plotting, discard stale results and prevent a queued old close event from aborting a reopened dialog.
- The fresh runtime returned 23 Swiss-selection and 54 Norwegian courses. Every displayed coordinate sequence was checked against a cached OSM way; all original 22 course matches remain. Both Lütschine branches and source attribution were inspected in the browser. Selected courses draw above overlapping hit targets.
- An independent assistant review found no remaining code blockers after the selected-course layering fix. This is software review, not human validation of scientific methods or operational claims.

Publication and merge status are recorded in the integration PR. Original branches are retained, and the original checkout is synchronized only while clean. No force push, destructive reset or data cleanup is part of this task.
