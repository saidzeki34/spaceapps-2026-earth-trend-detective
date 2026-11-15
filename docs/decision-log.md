# Decision log

| Date | Decision | Basis |
| --- | --- | --- |
| 2026-10-30 | main/develop and feature PR workflow proposed | Historical administration record |
| 2026-11-15 | Preparation ended; user explicitly confirmed competition start | User instruction |
| 2026-11-15 | Latest scope is documentation, module responsibilities, folders and empty files only; teammates write code | User correction supersedes the broader handoff |
| 2026-11-15 | Preserve generated implementation separately at archive/generated-implementation, commit 165e09b | Nothing lost; archive is not accepted main implementation |
| 2026-11-15 | Verify main remained at 6576023 with only prior administrative/research content before skeleton work | Remote inspection; no implementation revert needed |
| 2026-11-15 | Shared skeleton and future feature PRs target main; preserve develop/work/* | User's shared starting-point request |
| 2026-11-15 | No algorithms, integrations, UI, models, database schemas or tests in this delivery | Explicit scope limit |
| 2026-11-15 | Reorganize placeholders into ui and trend first, risk_assessment later, predictionmodel much later; shared holds common inputs and source access | User's section proposal; documentation and empty files only |
| 2026-11-15 | Move historical analysis to trend, figures to ui/charts, models to predictionmodel and data/services/contracts/config to shared; add subsection placeholders | No implementation imported from the archive; risk_assessment uses the corrected spelling |
