"""
Step 1 – Scarica i dati grezzi.

  python 01_download.py               # tutto ciò che serve al toy model
  python 01_download.py --only meteo  # solo Open-Meteo storico
  python 01_download.py --only pvgis|eurostat|forecast|nasa

I file vengono salvati in data/raw/. Se un file esiste già non viene riscaricato,
quindi puoi interrompere e rilanciare senza problemi.
"""
import argparse
import json
import time

import pandas as pd
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # usa sempre la config di questa cartella
import df_config as C

C.RAW.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()


def get_json(url, params, tries=4, pause=2.0):
    """GET con retry semplice (rate limit / errori temporanei)."""
    for i in range(tries):
        r = SESSION.get(url, params=params, timeout=120)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            wait = pause * (2 ** i)
            print(f"   {r.status_code}, riprovo tra {wait:.0f}s")
            time.sleep(wait)
            continue
        raise RuntimeError(f"{r.status_code} {r.url}\n{r.text[:500]}")
    raise RuntimeError(f"Troppi tentativi falliti: {url}")


# --------------------------------------------------------------------------
# 1. Open-Meteo Historical (ERA5) – meteo orario per punto e per anno
# --------------------------------------------------------------------------
def download_meteo():
    url = "https://archive-api.open-meteo.com/v1/archive"
    out_dir = C.RAW / "openmeteo"
    out_dir.mkdir(exist_ok=True)
    for name, lat, lon, *_ in C.POINTS:
        for year in range(C.YEAR_START, C.YEAR_END + 1):
            f = out_dir / f"{name}_{year}.csv"
            if f.exists():
                continue
            print(f"Open-Meteo {name} {year}")
            js = get_json(url, {
                "latitude": lat, "longitude": lon,
                "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
                "hourly": "temperature_2m,wind_speed_100m,shortwave_radiation",
                "wind_speed_unit": "ms",
                "timezone": "UTC",
            })
            df = pd.DataFrame(js["hourly"]).rename(columns={
                "temperature_2m": "t2m", "wind_speed_100m": "ws100", "shortwave_radiation": "ghi"})
            df.to_csv(f, index=False)
            time.sleep(0.5)   # gentile con l'API gratuita


# --------------------------------------------------------------------------
# 2. PVGIS – resa annua di 1 kWp per punto (serve a tarare il CF solare)
# --------------------------------------------------------------------------
def download_pvgis():
    url = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
    f = C.RAW / "pvgis_yield.csv"
    if f.exists():
        return
    rows = []
    for name, lat, lon, *_ in C.POINTS:
        print(f"PVGIS {name}")
        js = get_json(url, {
            "lat": lat, "lon": lon, "peakpower": 1, "loss": 14,
            "optimalangles": 1, "outputformat": "json",
        })
        fixed = js["outputs"]["totals"]["fixed"]
        monthly = {f"E_m_{m['month']:02d}": m["E_m"] for m in js["outputs"]["monthly"]["fixed"]}
        rows.append({"point": name, "E_y_kWh_per_kWp": fixed["E_y"], **monthly})
        time.sleep(0.3)
    pd.DataFrame(rows).to_csv(f, index=False)


# --------------------------------------------------------------------------
# 3. Eurostat – gradi giorno (nrg_chddr2_a) e quota rinnovabili (nrg_ind_ren)
# --------------------------------------------------------------------------
def jsonstat_to_df(js):
    """Converte una risposta JSON-stat 2.0 di Eurostat in un DataFrame piatto."""
    ids, sizes = js["id"], js["size"]
    cats = []
    for d in ids:
        idx = js["dimension"][d]["category"]["index"]
        order = sorted(idx, key=idx.get) if isinstance(idx, dict) else idx
        cats.append(order)
    rows = []
    for k, v in js["value"].items():
        k = int(k)
        coords = []
        for size in reversed(sizes):
            coords.append(k % size)
            k //= size
        coords.reverse()
        rows.append({d: cats[i][c] for i, (d, c) in enumerate(zip(ids, coords))} | {"value": v})
    return pd.DataFrame(rows)


def download_eurostat():
    base = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    jobs = {
        # gradi giorno annuali: livello paese + regioni NUTS2 del paese
        "nrg_chddr2_a": {"geo": None, "sinceTimePeriod": C.YEAR_START},
        # quota di rinnovabili (totale, elettricità, riscaldamento, trasporti)
        "nrg_ind_ren": {"geo": C.COUNTRY, "sinceTimePeriod": C.YEAR_START},
    }
    for code, flt in jobs.items():
        f = C.RAW / f"eurostat_{code}.csv"
        if f.exists():
            continue
        print(f"Eurostat {code}")
        params = {"format": "JSON", "lang": "EN", "sinceTimePeriod": flt["sinceTimePeriod"]}
        if flt["geo"]:
            params["geo"] = flt["geo"]
        df = jsonstat_to_df(get_json(base + code, params))
        if code == "nrg_chddr2_a":   # tieni solo il paese e le sue regioni
            df = df[df["geo"].str.startswith(C.COUNTRY)]
        df.to_csv(f, index=False)


# --------------------------------------------------------------------------
# 4. Previsione ensemble attuale (per la parte "tra X giorni")
#    Nota: Open-Meteo conserva i singoli membri solo per pochi giorni,
#    quindi questa è la previsione di OGGI, non uno storico.
# --------------------------------------------------------------------------
def download_forecast():
    url = "https://ensemble-api.open-meteo.com/v1/ensemble"
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d_%H")
    out_dir = C.RAW / "ensemble" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, lat, lon, *_ in C.POINTS:
        f = out_dir / f"{name}.csv"
        if f.exists():
            continue
        print(f"Ensemble {C.ENSEMBLE_MODEL} {name}")
        js = get_json(url, {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,wind_speed_100m,shortwave_radiation",
            "models": C.ENSEMBLE_MODEL, "forecast_days": C.FORECAST_DAYS,
            "wind_speed_unit": "ms", "timezone": "UTC",
        })
        pd.DataFrame(js["hourly"]).to_csv(f, index=False)
        time.sleep(0.5)
    print(f"Previsione salvata in {out_dir}")


# --------------------------------------------------------------------------
# 5. (Opzionale) NASA POWER – seconda fonte per il modello generativo
# --------------------------------------------------------------------------
def download_nasa():
    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    out_dir = C.RAW / "nasa_power"
    out_dir.mkdir(exist_ok=True)
    for name, lat, lon, *_ in C.POINTS:
        for year in range(C.YEAR_START, C.YEAR_END + 1):
            f = out_dir / f"{name}_{year}.csv"
            if f.exists():
                continue
            print(f"NASA POWER {name} {year}")
            js = get_json(url, {
                "parameters": "WS50M,ALLSKY_SFC_SW_DWN,T2M", "community": "RE",
                "latitude": lat, "longitude": lon,
                "start": f"{year}0101", "end": f"{year}1231",
                "format": "JSON", "time-standard": "UTC",
            })
            p = js["properties"]["parameter"]
            df = pd.DataFrame(p)
            df.index = pd.to_datetime(df.index, format="%Y%m%d%H")
            df.index.name = "time"
            df.replace(-999, pd.NA).to_csv(f)
            time.sleep(1.0)


STEPS = {
    "meteo": download_meteo, "pvgis": download_pvgis, "eurostat": download_eurostat,
    "forecast": download_forecast, "nasa": download_nasa,
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(STEPS), help="scarica una sola fonte")
    args = ap.parse_args()
    todo = [args.only] if args.only else ["meteo", "pvgis", "eurostat", "forecast"]
    for s in todo:
        STEPS[s]()
    print("Fatto.")
