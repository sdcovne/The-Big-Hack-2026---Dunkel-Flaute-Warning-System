# Data card — `hourly_country.csv`

Hourly national series for **Germany**, **2010-01-01 00:00 → 2025-12-31 23:00**: 140,256 hours, complete, no gaps. Timestamps are a continuous hourly index with no daylight-saving changes.

It is the only raw input of the project. Both the AI generator (`scripts/addestra_generatore.py`) and the 2029-30 scenario (`scripts/genera_dataset_2029_2030.py`) are built from it.

## Columns and provenance

| Column | Unit | What it is | Source / how it was built |
|---|---|---|---|
| `time` | – | Hour (start of interval) | – |
| `cf_wind` | 0–1 | Wind capacity factor | **ERA5 reanalysis** wind speed at 100 m, retrieved through the **Open-Meteo Historical Weather API** at 9 points weighted over Germany. Converted to CF with a standard turbine power curve: zero below about 3 m/s, full output from about 12 m/s, cut-out above about 25 m/s. Fixed fleet: no trend over the years. |
| `cf_solar` | 0–1 | Solar PV capacity factor | **ERA5** surface irradiance (Open-Meteo, same points) / 1000 W/m², with a temperature correction. Annual yield cross-checked against **PVGIS**. |
| `t2m` | °C | 2 m air temperature, national average | **ERA5** via Open-Meteo, same points |
| `hdd_day` | °C·day | Heating degree-days of the day | Derived: max(18 °C − daily mean temperature, 0) |
| `demand_gw` | GW | Electricity demand | **Modelled, not metered** — see below |
| `demand_essential_gw` | GW | Essential demand | Derived: 0.65 × `demand_gw` (scenario assumption) |

### Demand is modelled
`demand_gw` is a synthetic load built from calendar and temperature. It is not the metered German load. Analysis of the file shows:
- **A simple model explains almost all of it.** An hour-of-week profile + month + `hdd_day` explains 99.6% of the variance (R² = 0.996).
- **The level is flat at about 500 TWh/year** in every year 2010–2025. That is the order of magnitude of German consumption, but without the real year-to-year changes: no 2020 COVID dip, no 2022–23 energy-crisis reduction.
- **Holidays are only weakly visible.** At noon on 25 December demand is about 5% below a December weekday; metered load drops much more.

For this project that is acceptable: the event rule depends only on weather, and the 2030 scenario rescales demand anyway. For calibrated studies it should be replaced by metered load, as listed below.

## Upstream sources
- **ERA5 reanalysis** (Copernicus Climate Change Service / ECMWF). Hersbach, H. et al. (2020), *The ERA5 global reanalysis*, Q. J. R. Meteorol. Soc. 146, doi:10.1002/qj.3803.
- **Open-Meteo Historical Weather API** (ERA5 time series by coordinates, back to 1940): https://open-meteo.com/en/docs/historical-weather-api
- **PVGIS** (European Commission JRC): photovoltaic yield used to cross-check the solar capacity factor.
- **Metered load for future replacement or validation of `demand_gw`:** ENTSO-E Transparency Platform (actual total load, Germany) or SMARD (Bundesnetzagentur).

## Known checks
- **Real Dunkelflauten are present without tuning:**
  - 16–25 January 2017;
  - early November 2024 (low point on 6/11);
  - 11–13 December 2024;
  - 25–28 December 2024.
- **Wind–temperature anomalies are positively correlated** (about +0.40 in Oct–Mar daily anomalies): calm comes with cold.

## To be confirmed by the team before publication
- [ ] Exact coordinates and weights of the 9 Open-Meteo points
- [ ] Exact power-curve parameters and solar temperature correction
- [ ] Script that generated this file (`scripts/` should include it for full end-to-end reproducibility)
- [ ] How `demand_gw` was modelled (profile and calibration source)
