# Source and licence ledger

This main-branch skeleton contains no application data, runtime dependencies, scientific methods or computed results.

| Material | Use | Record |
| --- | --- | --- |
| User project handoff (3) and subsequent corrections | Context and folder/module planning only; latest correction controls scope | 2026-11-15; user-supplied, not redistributed |
| Existing research pack | Reading references with original access/verification limits | See research/resource-index.md and research/reading-notes.md |
| OpenAI Codex assistance | Repository documentation, placeholder structure and Git administration | 2026-11-15; human team owns implementation |
| Earlier generated implementation | Preserved separately, not incorporated into main | archive/generated-implementation at 165e09b contains its own source ledger |
| CAMELS-CH (Höge et al. 2023), doi:10.5281/zenodo.7784632 | Observed daily discharge and meteorology plus static attributes for the trend section (mountain_water/trend). Version, checksum and licence are written to data/raw/camels_ch/v<version>/provenance.json at download | Integrated 2026-11-15; v0.9 downloaded and processed by the team on 2026-11-15; data stays out of Git |
| Python libraries: numpy, pandas, pyarrow, scipy, pymannkendall, plotly, requests, pytest | Parsing, statistics, trend tests and figures | Declared in pyproject.toml, 2026-11-15 |
| Anthropic Claude Code assistance | Backend plan and implementation of mountain_water/trend, tests/trend and pyproject.toml | 2026-11-15; team reviews methods and results |

Preparation was assisted by ChatGPT/Codex on 2026-11-13. The archive preserves the actual earlier implementation work; this skeleton does not conceal it or claim those capabilities.

When teammates use data or software, add provider/product/version, URL/DOI, units, spatial/temporal coverage, quality information, retrieval date, transformations, licence and attribution. Do not label merely researched resources as used inputs.
