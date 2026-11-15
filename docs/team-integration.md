# Team integration handoff — 2026-11-15

This is the historical first integration (PR #9), before the submitted web UI and Norway/station backend updates. See [submitted-handoffs.md](submitted-handoffs.md) for the current state; the Streamlit checks and disconnected-UI description below apply only to that earlier checkpoint.

The user requested that available team work be combined onto main without losing ongoing progress. This is a source integration, not completion of the application.

## Included and preserved

| Work | Source | Treatment |
| --- | --- | --- |
| Existing shared skeleton and service/editor cleanup | main at ea95b10 | Retained as the integration base |
| Jonathan's CAMELS-CH trend backend | feature/backend-camels-ch-trends at a92fbbd, PR #6 | Included through work/backend; original commits and branch retained |
| Jonathan's GLDAS extension | feature/backend-gldas at 18276d1, PR #8 | Included through work/backend at c7f29ea; original commits and branch retained |
| Saved local RivaScope UI, identified by the user as Claude's work | mountain_water/ui in the active checkout | Copied to a separate worktree and committed as 675913d on archive/ui-snapshot-20261115 before merging |
| Existing develop, work/analysis, work/data, work/frontend, work/presentation, work/visualization and old setup/skeleton branches | Branch inventory at integration time | Their tips were already ancestors of main; retained without resetting or deleting them |
| Earlier generated implementation | archive/generated-implementation at 165e09b | Preserved separately, excluded from main under the prior explicit scope correction |
| DFL's commercial file | Not found locally or on published branches | Skipped at the user's explicit instruction |
| Local docs/brainstorming.md | Empty untracked file | Left untouched in the active checkout |

No other distinct published teammate implementation was found at the inventory cutoff. Work only on someone else's computer, ignored local files and unsaved editor buffers cannot be collected by merging remote branches.

The only merge conflict was append-only entries in docs/decision-log.md; entries from both sides were retained. Backend source and tests were not rewritten. UI source and assets match the preservation checkpoint; the map README's source-ledger note was updated. The optional ui dependency installs the Streamlit version needed by this UI. Current documentation replaces obsolete skeleton-only instructions while retaining the historical record.

## What remains unfinished

- UI data_source.CONNECTED remains false. Screens show empty states or explicitly labelled synthetic sample previews; the backend's results are not wired into them.
- Shared contracts and assessment coordination, risk assessment and the team's prediction/physics model remain placeholders.
- The trend backend's live access and scientific claims retain the validation limits in its README. This integration does not download observations, run a real-data analysis or validate scientific findings.
- The map's external tiles, source terms and geometry retain the review limits in its README.

## Validation

Checks are performed in tmp/team-integration, separate from the live UI checkout. The existing Python environment is used without modifying it; missing pymannkendall 1.4.3 and shapely 2.2.0 are installed only into tmp/integration-check-deps for these checks.

- Streamlit AppTest loaded six states without exceptions: menu, Europe, country, river empty state, river sample preview and prediction sample preview. This exercises Python rendering, not browser JavaScript, map interaction or external tile availability.
- The trend CLI help command succeeds without downloading data.
- Existing backend suite: 26 passed in 100.84 seconds, using python -m pytest -q --tb=short --basetemp=tmp/pytest-team-integration-2. The temp directory's parent was created first. Initial attempts hit the sandbox's default temp-folder restriction and then a missing temp parent; no test or backend source changes were needed. Final GitHub check/review status is recorded in the PR.
- No removed service/editor configuration was reintroduced. The live UI files were verified byte-for-byte against the preservation snapshot before publication.

## Continue safely

All original branches remain available. Use feature branches and PRs targeting main from now on; see SETUP.md. Writers on an older branch can merge origin/main into their own branch after checkpointing their work.

The original active checkout is deliberately not switched, stashed, reset or fast-forwarded while Claude may be editing it. The combined checkout is tmp/team-integration on integration/team-main-20261115. A remote main merge does not update the original checkout's files; coordinate with its active writer before changing that checkout.
