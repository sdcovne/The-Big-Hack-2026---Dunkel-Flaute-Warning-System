# ⚡ Dunkelflaute Early Warning System

**See the risk → measure it → decide in time.**

In a power grid built mostly on wind and solar, the biggest systemic risk is a *Dunkelflaute*: several days with almost no wind and sun, typically during a cold winter anticyclone. This prototype generates the events history has not shown yet with a small generative AI model, simulates them on a 2030 German grid (Digital Twin), and tells grid operators, industry and energy communities what to do, and by when, days before the event arrives.

> *"We cannot stop the Dunkelflaute. We can stop being surprised by it."*

---

## Contents
- [What the app does](#what-the-app-does)
- [Quick start](#quick-start)
- [Using the app](#using-the-app)
- [Repository structure](#repository-structure)
- [How it works](#how-it-works)
- [Key results](#key-results)
- [Assumptions](#assumptions)
- [Limitations](#limitations)
- [Reproducing data and model](#reproducing-data-and-model)
- [Use of AI](#use-of-ai)
- [Data sources](#data-sources)
- [References](#references)

---

## What the app does

| Step | What happens | Where in the app |
|---|---|---|
| **① See** | A forecast of the coming Dunkelflaute: 60 forecast scenarios, event probability, uncertainty band of wind + solar output against electricity demand | Alert box + tab ① |
| **② Measure** | A Digital Twin of the 2030 grid balances demand and supply hour by hour (wind, solar, reserve plants, imports, storage, demand reduction) and returns the key number: **GWh of essential electricity demand left uncovered** | Result section + tab ② |
| **③ Decide** | Five mitigation actions, each with a deadline (T−10 … T−1). Moving the lead-time slider shows which actions are still possible and how much essential demand they protect compared with doing nothing | Action cards + tab ③ |
| **🤖 AI approach** | How the generative model works, how accurate it is (3 KPIs + comparison table), how much storage the grid would need if sized on history vs on generated events, and the current limitations | Tab 🤖 |

The interface is available in **Italian and English** (flag switch at the top right).

---

## Quick start

Requirements: **Python 3.10+**.

```bash
git clone <repository-url> dunkelflaute-ews
cd dunkelflaute-ews
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run src/app.py
```

The app opens at `http://localhost:8501`.

**Run the command from the repository root.** Streamlit reads the light theme from `.streamlit/config.toml` in the current folder, and the app finds `data/` and `models/` from there.

- **Language:** click 🇬🇧 EN / 🇮🇹 IT at the top right.
- **Fonts:** the app loads the Inter font from Google Fonts. Offline, it falls back to the system font.

---

## Using the app

### 1. Alert box and lead-time slider
At the top of the page, the slider **"Days of warning before the event"** (T−0 … T−14) sets *today* relative to the event. Everything on the page updates with it.

The alert box shows five indicators. Each has a **?** that explains how it is calculated:

| Indicator | Meaning |
|---|---|
| **Event probability** | Share of 60 forecast scenarios in which wind + solar stay below 35% of expected output for at least 2 days |
| **Expected duration** | Median duration of the event in the forecast scenarios |
| **Wind + solar drop** | Expected → forecast output in GW, and the drop in % |
| **Energy gap** | Demand minus wind and solar during the event (GWh) |
| **Essential demand uncovered** | Share of national essential electricity demand (65% of the total) left without power if we act today |

Alert levels:

| Level | When |
|---|---|
| 🟢 Green | Probability < 10% |
| 🔵 Pre-alert | Probability 10–30% |
| 🟠 Orange | Event likely, essential demand protected |
| 🔴 Red | Essential demand still uncovered |

### 2. The result
- **Today → Dunkelflaute arrives → actions still possible today.** Three cards with the dates and the number of actions still possible.
- **Action cards.** Five cards, one per mitigation action, marked *✓ still possible* or *✗ expired*. The superscript number links to the **Notes** at the bottom of the page, which give the assumption and source for each action.
- **"Do nothing" vs "Act today · T−X".** A comparison of essential demand not served, hours uncovered and cost of the crisis. The **?** on the cost row shows the formula and the calculation item by item.
- **Headline KPI.** GWh of essential demand protected by the plan.

### 3. Tabs

| Tab | Content |
|---|---|
| **① See** | Forecast of wind + solar output (median and 25–75% band), simulated scenario, total and essential electricity demand. Toggle: *24 h moving average* |
| **② Measure** | Hourly balance. By default: solar, wind, total demand, essential demand. *Show mitigation effects* adds the five options and the essential demand not served. Comparison table with/without warning; scenario assumptions |
| **③ Decide** | Timeline of the five actions with "today" marked; curve of essential demand not served vs days of warning ("each day of warning is worth N GWh"); message sent to energy communities and citizens |
| **🤖 AI approach** | Why AI; generator accuracy (3 KPIs + table); why the generated maximum duration is longer; duration distribution; learned weather regimes; storage needed (history vs synthetic); forecast scenarios; limitations |

### 4. Sidebar
- **Presentation mode.** A guided 5-step demo:
  1. warning at T−7;
  2. if we do nothing;
  3. with the plan;
  4. stress test with a 1-in-100 event;
  5. what one day of warning is worth.
- **2030 power grid assumptions.**

  | Assumption | Default |
  |---|---|
  | Storage capacity | 80 GWh |
  | Storage power | 20 GW |
  | Backup plants | 40 GW |
  | Fuel available for the event | 4,000 GWh |
  | Storage charge on arrival without warning | 50% |

---

## Repository structure

```
dunkelflaute-ews/
├── README.md
├── requirements.txt
├── .streamlit/
│   └── config.toml                  # light theme
├── src/
│   ├── app.py                       # Streamlit interface (IT/EN)
│   ├── motore.py                    # engine: Digital Twin, actions, forecast scenarios, analyses (no Streamlit)
│   └── testi.py                     # all interface texts, Italian and English
├── models/
│   └── generatore_params.json       # trained generator: regimes, scenarios, climatology, validation
├── data/
│   ├── simulazione_dunkelflaute_nov2029_gen2030.csv   # hourly 2030 scenario used by the app
│   └── raw/
│       └── hourly_country.csv       # hourly Germany 2010–2025: wind/solar CF, temperature, demand (see Data sources)
├── scripts/
│   ├── addestra_generatore.py       # trains the AI generator → models/generatore_params.json
│   └── genera_dataset_2029_2030.py  # builds the 2029-30 scenario → data/simulazione_…csv
└── docs/
    └── AI_approach.pdf              # deep dive on the AI approach
```

Module and variable names are in Italian (`motore` = engine, `testi` = texts); the code is commented.

---

## How it works

```
data/raw/hourly_country.csv (2010–2025)
   │
   ├── scripts/genera_dataset_2029_2030.py ──► data/simulazione_dunkelflaute_nov2029_gen2030.csv
   │      2030 grid, demand +12.5%, 3-day event at −80% of expected output
   │
   └── scripts/addestra_generatore.py ──────► models/generatore_params.json
          AR-HMM generator, 10,000 synthetic winters, 1-in-10/100/1000 events, validation
                                    │
                                    ▼
                         src/app.py  +  src/motore.py
             forecast scenarios → Digital Twin → actions with deadlines → KPIs
```

### The 2030 scenario (dataset)
- **Period.** November 2029 – January 2030, hourly, 2,208 hours.
- **Wind and solar.** Output = capacity factor × capacity: 439 GW of wind + solar, split 0.65 / 0.35, i.e. 285 GW wind and 154 GW solar.
- **Demand.** Sampled from the historical distribution, conditioned on hour, day type and date, with growth to 2030 by time band: night +14%, morning +10%, afternoon +9%, evening +15%; +12.5% on average. Essential demand = 65% of the total.
- **Event.** 72 hours from 10 December 2029 06:00, with wind + solar output at 20% of expected (−80%) and 18-hour ramps in and out.

### The AI generator
An **autoregressive Hidden Markov Model** with three weather regimes (anticyclone, mixed, stormy).
- **Data.** Daily wind + solar output relative to expected, and temperature anomaly, for 15 winters (Nov–Jan 2010–2025).
- **Training.** Expectation–Maximisation (Baum–Welch), without labels.
- **What it learns.** How long weather regimes persist and that calm wind comes with cold.
- **Output.** 10,000 synthetic winters, from which the 1-in-10, 1-in-100 and 1-in-1000 events are extracted.

Details, equations and validation: [`docs/AI_approach.pdf`](docs/AI_approach.pdf).

### Forecast scenarios
For each lead time X, the app builds 60 scenarios.
- With probability exp(−X/16) a scenario "sees" the event, perturbed in intensity, duration and arrival time.
- Otherwise it is a normal winter.
- The event probability is the share of scenarios that meet the event rule.

### Digital Twin (hourly dispatch)
**Outside the event:** surplus charges storage, then is curtailed. A deficit is covered by storage, then by backup plants.

**During the event, without a plan:**
1. storage;
2. backup plants (within the fuel stock);
3. sudden cuts of non-essential demand, at most 50% of it;
4. the rest is **essential demand not served**.

**During the event, with the plan:**
1. planned demand reductions;
2. backup plants, including the extra plants;
3. imports;
4. storage, used only for the part of essential demand that cuts cannot protect;
5. targeted cuts of non-essential demand, at most 55% of it.

### The five actions

| Deadline | Action | Effect |
|---|---|---|
| T−10 | Reserve plants: fuel, postponed maintenance | +3 GW, +4,000 GWh of fuel |
| T−7 | Import contracts with neighbouring countries | +3 GW |
| T−5 | Agreements with industry to cut demand | −3 GW |
| T−3 | Charge storage and reserve it for essentials | storage full on arrival |
| T−1 | Alert communities and citizens, planned cuts | −2 GW in daytime, −1% demand, targeted cuts |

Assumptions and sources are in the app's **Notes**: Germany's lignite security reserve, DIW on the capacity reserve, the AbLaV interruptible-load scheme, Wood Mackenzie on batteries, France's EcoWatt.

### Cost model
Cost of the crisis = Σ (energy × price) + fixed costs of the actions launched.

| Item | Price |
|---|---|
| Backup plants | €120/MWh |
| Imports | €250/MWh |
| Planned demand reductions | €100/MWh |
| Non-essential cuts | €100/MWh if planned, €500/MWh if sudden |
| Essential demand not served (value of lost load) | €5,000/MWh |

---

## Key results

With the default assumptions:

**Dataset event** (3 days, −80%), essential demand uncovered by lead time:

| Lead time | Essential demand uncovered |
|---|---|
| Do nothing (T0) | 411 GWh (11.8%) |
| T−1 / T−2 | 287 GWh (8.2%) |
| T−3 / T−4 | 207 GWh (5.9%) |
| T−5 / T−6 | 147 GWh (4.2%) |
| T−7 … T−9 | 37 GWh (1.1%) |
| T−10 | 0 |

**Event probability** for the dataset event: 15% at T−14, 48% at T−7, 78% at T−3, 100% at T0.

**Stress test (1-in-100 winters, 10 days)**, essential demand uncovered:

| Lead time | Essential demand uncovered |
|---|---|
| Do nothing | 6,496 GWh |
| Plan at T−7 | 5,146 GWh |
| Plan at T−10 | 1,192 GWh |

**Generator accuracy:**

| KPI | Value |
|---|---|
| Similarity of event durations, real vs generated | 91% |
| Unseen winters (2022-25) judged plausible | 3 of 3 |
| Likelihood on unseen winters vs a model without regimes | 2.6× higher |

**Storage needed** for zero uncovered essential demand, with the plan at T−7:

| Sizing basis | Storage needed |
|---|---|
| History only (worst event 2010–25) | 3,977 GWh |
| History + synthetic (1-in-100 winters) | 5,229 GWh |
| Extreme stress (1-in-1000 winters) | 8,320 GWh |

> Figures are illustrative: the value lies in the chain *see → measure → decide*, where each component can be replaced with a more accurate one.

---

## Assumptions

| Item | Value |
|---|---|
| Wind + solar capacity | 439 GW, split 0.65 / 0.35 |
| Demand growth to 2030 | +12.5% on average (EU outlooks: EVs, heat pumps, data centres) |
| Essential share of demand | 65% |
| Backup plants | 40 GW, fuel for about 100 h |
| Storage | 80 GWh / 20 GW (batteries and pumped hydro) |
| Event rule | Wind + solar below 35% of expected for ≥ 2 consecutive days |
| Forecast memory | exp(−lead time / 16 days) |

---

## Limitations
- **Single node.** Germany is one grid, with no regional flows; imports are a fixed amount.
- **Few training winters.** 15 winters (Nov–Jan); 1-in-1000 events are model extrapolations.
- **The generator is not a forecaster.** One day ahead it catches 27% of Dunkelflaute days (precision 75%), and none at 2–3 days. Week-ahead forecasting needs weather models.
- **Simulated forecast.** Probability and uncertainty come from constructed scenarios, not from real weather forecasts.
- **Actions and costs** are scenario assumptions drawn from public sources, not calibrated values.
- **Simplified operation.** Rule-based dispatch, a single aggregate storage, essential demand fixed at 65%.
- **Simulated input data.** The dataset event is constructed.
- **Prototype.** A Streamlit demonstration, not a multi-user production service.

**Next steps**
- Verify the forecast on archived ECMWF ensemble forecasts (open archive from April 2024).
- Model a multi-node European grid.
- Calibrate actions and costs with a grid operator in a pilot.
- Move to neural generators when more data is available.

---

## Reproducing data and model

Both scripts use fixed random seeds: running them reproduces the files shipped in the repository exactly.

```bash
# 1. Retrain the AI generator (about 1 minute)
python scripts/addestra_generatore.py data/raw/hourly_country.csv models/generatore_params.json

# 2. Rebuild the 2029-30 hourly scenario (a few seconds)
python scripts/genera_dataset_2029_2030.py data/raw/hourly_country.csv data/simulazione_dunkelflaute_nov2029_gen2030.csv
```

---

## Use of AI
- **In the product:** a probabilistic generative model, an autoregressive Hidden Markov Model learned without labels by Expectation–Maximisation. It generates plausible Dunkelflaute events beyond the historical record. It is validated on unseen winters and used for stress tests and storage sizing. See [`docs/AI_approach.pdf`](docs/AI_approach.pdf).
- **In development:** code, analyses and documentation were developed with the help of an AI assistant (Claude, Anthropic).

---

## Data sources

All datasets shipped in this repository are open and are produced from the sources below. The chain is:

```
ERA5 reanalysis (Copernicus / ECMWF) ──► Open-Meteo Historical Weather API ──► data/raw/hourly_country.csv
                                                                                  │
          scripts/addestra_generatore.py ◄────────────────────────────────────────┤
                    │                                                             │
                    ▼                                                             ▼
     models/generatore_params.json                   scripts/genera_dataset_2029_2030.py
                                                                                  │
                                                                                  ▼
                                              data/simulazione_dunkelflaute_nov2029_gen2030.csv
```

### Datasets in the repository

| File | What it is | Built from | How |
|---|---|---|---|
| `data/raw/hourly_country.csv` | Hourly Germany 2010-01-01 → 2025-12-31 (140,256 hours, no gaps): wind and solar capacity factors, temperature, heating degree-days, electricity demand | ERA5 via Open-Meteo (weather); demand model (see below) | Column by column in the table below |
| `models/generatore_params.json` | Trained AI generator: weather regimes, transition matrix, climatology of expected wind/solar output, 1-in-10/100/1000 scenarios, validation | `hourly_country.csv` (Nov–Jan, 2010-11 … 2024-25) | `scripts/addestra_generatore.py` (fixed seeds, reproducible) |
| `data/simulazione_dunkelflaute_nov2029_gen2030.csv` | Hourly 2030 scenario, Nov 2029 – Jan 2030 (2,208 hours), with a 3-day Dunkelflaute at −80% of expected output | `hourly_country.csv` + 2030 assumptions | `scripts/genera_dataset_2029_2030.py` (seed 42, reproducible) |

### `hourly_country.csv`: columns and provenance

| Column | Unit | Source / construction |
|---|---|---|
| `time` | – | Hourly index, continuous (no daylight-saving changes) |
| `cf_wind` | 0–1 | **ERA5** wind speed at 100 m, retrieved through the **Open-Meteo Historical Weather API** at 9 points weighted over Germany. Converted to capacity factor with a standard turbine power curve: zero below about 3 m/s, full output from about 12 m/s, cut-out above about 25 m/s. Fixed fleet: no trend over the years. |
| `cf_solar` | 0–1 | **ERA5** surface irradiance (Open-Meteo, same points) / 1000 W/m², with a temperature correction. Annual yield cross-checked against **PVGIS**. |
| `t2m` | °C | **ERA5** 2 m temperature (Open-Meteo, same points) |
| `hdd_day` | °C·day | Derived: max(18 °C − daily mean temperature, 0) |
| `demand_gw` | GW | **Modelled, not metered**: hour-of-week profile + season + heating degree-days, at about 500 TWh/year (the order of magnitude of German consumption) |
| `demand_essential_gw` | GW | Derived: 0.65 × `demand_gw` (scenario assumption) |

**About the demand column.** It is a synthetic load, not the metered German load:
- an hour-of-week profile + month + `hdd_day` explains 99.6% of its variance;
- the annual level is flat at about 500 TWh, with no 2020 COVID dip and no 2022–23 energy-crisis reduction;
- holidays are only weakly visible.

This is acceptable here because the Dunkelflaute rule depends only on weather, and the 2030 scenario rescales demand anyway. For calibrated studies, replace it with metered load from the **ENTSO-E Transparency Platform** (actual total load, Germany) or **SMARD** (Bundesnetzagentur).

**Checks.** The real Dunkelflauten of 16–25 January 2017, early November 2024, 11–13 December 2024 and 25–28 December 2024 are found in the data without tuning. Wind and temperature anomalies are positively correlated (about +0.40 in Oct–Mar): calm comes with cold.

### 2030 scenario: external sources for the assumptions

| Assumption | Value | Source |
|---|---|---|
| Demand growth to 2030 | +12.5% on average; night +14%, morning +10%, afternoon +9%, evening +15% | Wood Mackenzie, *Europe Power Markets Strategic Planning Outlook 2026* (European demand +11% 2025→2030); Universidad Pontificia Comillas, *European Power Demand Forecast 2030* (+4% to +20% vs 2021) |
| Wind + solar capacity | 439 GW, split 0.65 / 0.35 | Team assumption (fleet producing about 130% of average demand) |
| Backup plants | 40 GW | Order of magnitude of German gas-fired capacity plus biomass |
| Essential share of demand | 65% | Scenario assumption (stated and adjustable in the code) |

### Sources for the mitigation actions
Shown in the app's Notes:
- **Reserve plants:** Germany's lignite security reserve, ready within 10 days of a call (oenergetice.cz, 2023); DIW Wochenbericht 49/2024 on the capacity reserve (about 2 GW outside the market).
- **Industry:** AbLaV interruptible-load scheme (up to 1.5 GW, 2012–2022): netztransparenz.de and the European Commission State aid decision.
- **Storage:** Wood Mackenzie (2026), European battery capacity 47 → 163 GW by 2030.
- **Communities:** France's EcoWatt saving campaigns.
- **Context, 2024 price spikes:** Bundesnetzagentur and Bundeskartellamt (2025), study of electricity price peaks during the Dunkelflauten of November and December 2024 (day-ahead peak €936/MWh on 12 December 2024).

### To be confirmed by the team before publication
- [ ] Exact coordinates and weights of the 9 Open-Meteo points
- [ ] Exact power-curve parameters and solar temperature correction
- [ ] The script that produced `hourly_country.csv` (add it to `scripts/` for end-to-end reproducibility from ERA5)
- [ ] How `demand_gw` was modelled (profile and calibration source)

## References
- Hersbach, H. et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.* 146, 1999–2049. doi:10.1002/qj.3803
- Open-Meteo Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api
- PVGIS, Photovoltaic Geographical Information System (European Commission, Joint Research Centre)
- ENTSO-E Transparency Platform; SMARD (Bundesnetzagentur): metered load for future validation
- Rabiner, L. R. (1989). A tutorial on hidden Markov models and selected applications in speech recognition. *Proc. IEEE* 77(2).

---

## License
Not yet specified. Add a `LICENSE` file before publishing the repository.
