# Reading notes for future AI sessions

Research context checked 2026-11-13. This is a concise reading guide, not a scientific design or an implementation specification. Resource IDs refer to [the inventory](resource-index.md). No region, product, algorithm, interface or database schema has been selected here.

## Challenge orientation

The official indexed challenge summary asks for exploration of Earth-system variables across time and place, including change magnitude and statistical significance. The complete Resources tab could not be fetched; verify it before committing to a dataset.

A mission/instrument name such as MODIS, OMI, AIRS or GPM does not uniquely specify a dataset. MERRA-2 and GLDAS are model/data-assimilation families, not interchangeable satellite measurements. For any eventual choice, read the exact product's provider documentation rather than inferring units, spatial resolution, time coverage or quality controls from the family name. These names are orientation from the challenge context, not a commitment to use every family.

## R01: Giovanni

Source: [NASA's user manual](https://giovanni.gsfc.nasa.gov/giovanni/doc/UsersManualworkingdocument.docx.html), especially Quick Start, Calculating Weighted Statistics, and time-series services.

The manual describes full access through Earthdata Login and authorization for the GES DISC archive; guest access is limited. It describes downloading plot source files, including netCDF. Do not interpret a navigable webpage as an authenticated data connection.

Spatial statistics use latitude-based weights for most services; shape boundaries introduce additional weighting. Missing/fill values are excluded. This matters when later comparing your output with Giovanni: identify the exact service, valid cells and weighting. The manual contains historical release notes, so use the current service documentation and exported metadata when details conflict. No data request was made in this preparation.

## R02 and R03: access still to verify

The hydrology tool and AppEEARS landing/help pages returned JavaScript shells to the text reader. Their links are available, but this preparation did not establish an API contract, current authentication behavior, available product list or successful export. Read their current documentation during the event before building a client. Do not invent endpoints from a portal URL.

## R04: NOAA CDO

Sources: [portal](https://www.ncei.noaa.gov/cdo-web/) and [API v2 documentation](https://www.ncei.noaa.gov/cdo-web/webservices/v2).

CDO provides weather/climate records and station metadata. The documented API requires a token and lists limits of five requests per second and 10,000 per day; verify limits again before use. Dataset, datatype, location and station identifiers are separate concepts. NOAA data are not automatically a substitute for the required NASA resource. No token was requested or data downloaded.

## R05: SeaWiFS literature note

James G. Acker, Erin McMahon, Suhung Shen, Thomas Hearty and Nancy Casey, *Time-Series Analysis of Remotely-Sensed SeaWiFS Chlorophyll in River-Influenced Coastal Regions*. [NTRS 20090042747](https://ntrs.nasa.gov/citations/20090042747); record publication date 2009-01-01, EARSeL eProceedings 8(2). NTRS labels the deposited document a preprint. Do not describe that deposit as an independently verified final published version.

The paper uses monthly SeaWiFS regional records, Giovanni exports, least-squares trends and significance assessment; it also examines anomalies. Read Methods (PDF pages 3–4) and the Statistical Methods discussion (from PDF page 17).

The main interpretation caution is optical interference: coastal chlorophyll retrievals can respond to sediment and colored dissolved organic matter. A trend in the retrieved quantity therefore needs physical interpretation and calibration context. Flood episodes can strongly affect the record. The historical paper describes arithmetic regional averaging, while the current Giovanni manual describes weighted statistics. Verify the processing version instead of assuming the two are identical.

This is a worked literature example, not validation of any future team result. No reported coefficient or regional result has been adopted for the project.

## R06 and partner resources

KNMI's [overview](https://climexp.knmi.nl/) describes observations, reanalyses and model data, plus statistical tools. It asks users to cite both Climate Explorer and original datasets. Its human-verification gate means unattended access should not be assumed.

The [SWOT mission page](https://www.asc-csa.gc.ca/eng/satellites/swot/) gives a December 16, 2022 launch and describes water-surface measurements. The ecosystem overview still calls SWOT “in development”; prefer the mission page for status. Inference: SWOT alone cannot supply a decades-long historical record, so record length needs checking before any long-term interpretation.

The [CSA SAR tutorial README](https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial) introduces QGIS/Python material and describes a modified MIT license. Read the actual license and data-specific terms before reuse; do not assume standard MIT terms or that imagery inherits the code license. R07/R08 are supplementary educational links. Neither has been used to establish scientific test assumptions here.

## Questions to carry into the event

These are general review questions, not a selected analysis pipeline:
- What does the variable physically measure, and what are its units, uncertainty, quality flags and missing-value conventions?
- Is the record long enough to distinguish a persistent change from seasonality or a few unusual events?
- Are measurements temporally dependent, and do the proposed confidence intervals/tests account for that?
- How are spatial weights, changing coverage and irregular observation times handled?
- Does searching many variables/regions create a multiple-testing issue?
- Is the reported effect size meaningful physically, beyond whether a threshold is crossed?
- Can a reader reproduce the region, time range, product/version, retrieval and transformations?
- What evidence supports a causal explanation beyond the existence of a trend?

Answer these with product documentation and appropriate primary statistical literature once the team chooses a method. No test has been selected or implemented in advance.
