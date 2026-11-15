# Source and licence ledger

The original main skeleton contained no application data or runtime dependencies. The team integration now includes the source code and display assets recorded below. Inherited source records are preserved; merging them is not independent verification of their scientific or licence claims.

| Material | Use | Record |
| --- | --- | --- |
| User project handoff (3) and subsequent corrections | Context and folder/module planning only; latest correction controls scope | 2026-11-15; user-supplied, not redistributed |
| Existing research pack | Reading references with original access/verification limits | See research/resource-index.md and research/reading-notes.md |
| OpenAI Codex assistance | Repository documentation, placeholder structure and Git administration | 2026-11-15; human team owns implementation |
| Earlier generated implementation | Preserved separately, not incorporated into main | archive/generated-implementation at 165e09b contains its own source ledger |
| CAMELS-CH (Höge et al. 2023), doi:10.5281/zenodo.7784632 | Observed daily discharge and meteorology plus static attributes for the trend section (mountain_water/trend). Version, checksum and licence are written to data/raw/camels_ch/v<version>/provenance.json at download | Integrated 2026-11-15; v0.9 downloaded and processed by the team on 2026-11-15; data stays out of Git |
| NASA GLDAS-2.1 Noah 0.25° 3-hourly (GLDAS_NOAH025_3H 2.1; Beaudoing & Rodell, NASA GES DISC), doi:10.5067/E7TYRXPJKWOQ, via the Giovanni Time Series API | Modelled runoff, snowmelt, precipitation, snowfall, air temperature, evapotranspiration and SWE for the CAMELS-CH mountain catchments (mountain_water/trend/gldas.py) | Integrated 2026-11-15. Requires an Earthdata Login token; API access and response format verified with a probe request on 2026-11-15; full download pending; data stays out of Git |
| Python libraries: numpy, pandas, pyarrow, scipy, pymannkendall, plotly, requests, pyshp, pyproj, shapely, pytest | Parsing, statistics, trend tests and figures | Declared in pyproject.toml, 2026-11-15 |
| Anthropic Claude Code assistance | Backend plan and implementation of mountain_water/trend (CAMELS-CH and GLDAS), tests/trend and pyproject.toml | 2026-11-15; team reviews methods and results |
| Local RivaScope UI, identified by the user as Claude's work | Existing screens, charts, sample previews, logo and map component in mountain_water/ui; no backend data connected | Saved-file checkpoint 675913d on archive/ui-snapshot-20261115, 2026-11-15; exact assistant/model version not verified |
| Streamlit | Existing UI runtime; optional ui dependency | Integration checked with installed 1.67.0; declared as streamlit>=1.67 |
| Natural Earth display geometry | Country outlines and simplified river lines for Norway and Switzerland, saved in ui/map_component/frontend/geodata.json; transformation script build_geodata.py | UI author documents 1:10m admin_0_countries, rivers_lake_centerlines and rivers_europe, public domain. Original retrieval date/version not recorded; preserved asset, not newly downloaded. Display geometry is not a catchment or observation dataset; see the map README for transformations and limits. |
| Esri World Imagery and World Boundaries and Places | Browser-loaded map imagery and labels | Existing UI includes attribution; no tile data committed by integration. Terms review remains pending as documented by the UI author. |
| Leaflet | Map interaction in frontend/index.html, loaded from unpkg.com | UI author records 1.9.4 / BSD-2-Clause; runtime uses an external CDN. No new vendoring by integration. |
| OpenAI Codex integration assistance | Branch inventory, UI preservation checkpoint, merge conflict resolution retaining both decision logs, setup/dependency documentation and local checks | 2026-11-15; no new scientific method, data download or deployment; live UI working files left untouched |

Preparation was assisted by ChatGPT/Codex on 2026-11-13. The archive preserves the actual earlier implementation work; this skeleton does not conceal it or claim those capabilities.

When teammates use data or software, add provider/product/version, URL/DOI, units, spatial/temporal coverage, quality information, retrieval date, transformations, licence and attribution. Do not label merely researched resources as used inputs.
