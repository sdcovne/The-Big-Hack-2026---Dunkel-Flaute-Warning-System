"""
Step 2 – Dai dati grezzi alle feature del toy model.

  python 02_features.py

Output in data/processed/:
  hourly_country.csv     serie oraria nazionale: CF eolico, CF solare, T, gradi giorno, domanda
  climatology.csv        medie di riferimento (per mese e per stagione invernale)
  events.csv             catalogo delle Dunkelflaute storiche con i parametri di scenario
  sizing.csv             N pale e M pannelli per il futuro 100% rinnovabile
  calibration.csv        controlli: resa PV vs PVGIS, gradi giorno vs Eurostat
  forecast_summary.csv   (se c'è una previsione) probabilità di Dunkelflaute per giorno
"""
import glob
import re

import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # usa sempre la config di questa cartella
import df_config as C

C.PROC.mkdir(parents=True, exist_ok=True)


# ==========================================================================
# 1. Conversione fisica: meteo -> fattori di capacità
# ==========================================================================
def wind_cf(ws):
    """Curva di potenza semplificata: cubica tra cut-in e rated, piatta fino al cut-out."""
    ws = np.asarray(ws, dtype=float)
    vi, vr, vo = C.WIND_CUT_IN, C.WIND_RATED, C.WIND_CUT_OUT
    cf = np.where(ws < vi, 0.0,
         np.where(ws < vr, (ws**3 - vi**3) / (vr**3 - vi**3),
         np.where(ws < vo, 1.0, 0.0)))
    return cf * C.WIND_LOSSES


def solar_cf(ghi, t2m):
    """CF solare da irraggiamento orizzontale e temperatura (modello semplice).
    Verrà poi scalato con un fattore per punto in modo che la resa annua coincida con PVGIS."""
    ghi = np.asarray(ghi, dtype=float)
    t_cell = np.asarray(t2m, dtype=float) + ghi / 800.0 * C.PV_NOCT_DELTA
    cf = ghi / 1000.0 * (1 + C.PV_GAMMA * (t_cell - 25.0)) * C.PV_PR
    return np.clip(cf, 0, 1)


# ==========================================================================
# 2. Lettura e aggregazione nazionale
# ==========================================================================
def load_point(name):
    files = sorted(glob.glob(str(C.RAW / "openmeteo" / f"{name}_*.csv")))
    if not files:
        raise FileNotFoundError(f"Nessun dato Open-Meteo per {name}: lancia prima 01_download.py")
    df = pd.concat(pd.read_csv(f) for f in files)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time").sort_index().interpolate(limit=3)


def pvgis_scale(name, cf_raw):
    """Fattore che allinea la resa annua del modello con PVGIS (kWh/kWp/anno)."""
    f = C.RAW / "pvgis_yield.csv"
    if not f.exists():
        return 1.0, np.nan
    pv = pd.read_csv(f).set_index("point")
    if name not in pv.index:
        return 1.0, np.nan
    target = pv.loc[name, "E_y_kWh_per_kWp"]
    model = cf_raw.groupby(cf_raw.index.year).sum().mean()   # kWh/kWp/anno del modello
    return target / model, target


def build_country():
    wind_w = np.array([p[3] for p in C.POINTS]); wind_w = wind_w / wind_w.sum()
    sol_w = np.array([p[4] for p in C.POINTS]); sol_w = sol_w / sol_w.sum()
    dem_w = np.array([p[5] for p in C.POINTS]); dem_w = dem_w / dem_w.sum()

    cf_w, cf_s, temp, calib = 0, 0, 0, []
    for i, (name, *_rest) in enumerate(C.POINTS):
        d = load_point(name)
        cw = pd.Series(wind_cf(d["ws100"]), index=d.index)
        cs_raw = pd.Series(solar_cf(d["ghi"], d["t2m"]), index=d.index)
        k, target = pvgis_scale(name, cs_raw)
        cs = (cs_raw * k).clip(upper=1)
        calib.append({"point": name, "pv_scale": round(k, 3), "pvgis_kWh_kWp": target,
                      "model_kWh_kWp": round(cs.groupby(cs.index.year).sum().mean(), 1),
                      "wind_cf_mean": round(cw.mean(), 3)})
        cf_w = cf_w + wind_w[i] * cw
        cf_s = cf_s + sol_w[i] * cs
        temp = temp + dem_w[i] * d["t2m"]

    h = pd.DataFrame({"cf_wind": cf_w, "cf_solar": cf_s, "t2m": temp}).dropna()
    return h, pd.DataFrame(calib)


# ==========================================================================
# 3. Domanda: profilo base + sensibilità al freddo (gradi giorno)
# ==========================================================================
def add_demand(h):
    # Gradi giorno in stile Eurostat: (18 - Tmedia) se Tmedia <= 15 °C, altrimenti 0
    tday = h["t2m"].resample("D").mean()
    hdd_day = np.where(tday <= C.HDD_THRESHOLD, C.HDD_BASE - tday, 0.0)
    hdd_day = pd.Series(hdd_day, index=tday.index)
    h["hdd_day"] = hdd_day.reindex(h.index, method="ffill")

    # Profilo base sintetico (forma tipica di un paese europeo, ora UTC ~ ora locale -1)
    hod, dow = h.index.hour, h.index.dayofweek
    daily = 1 + 0.12 * np.cos(2 * np.pi * (hod - 17) / 24) + 0.06 * np.cos(2 * np.pi * (hod - 10) / 12)
    weekly = np.where(dow >= 5, 0.88, 1.0)
    shape = pd.Series(daily * weekly, index=h.index)

    # Domanda = base * (1 + k * HDD); scala in modo che la media annua dia ANNUAL_DEMAND_TWH
    raw = shape * (1 + C.HEAT_SENSITIVITY_K * h["hdd_day"])
    mean_gw = C.ANNUAL_DEMAND_TWH * 1e3 / 8760
    h["demand_gw"] = raw / raw.mean() * mean_gw
    h["demand_essential_gw"] = C.ALPHA_ESSENTIAL * h["demand_gw"]
    return h


def eurostat_hdd_check(h):
    f = C.RAW / "eurostat_nrg_chddr2_a.csv"
    if not f.exists():
        return pd.DataFrame()
    es = pd.read_csv(f)
    es = es[(es["geo"] == C.COUNTRY) & (es["indic_nrg"] == "HDD")]
    es = es.assign(year=es["time"].astype(int)).set_index("year")["value"]
    ours = h["hdd_day"].resample("D").first().groupby(lambda t: t.year).sum()
    out = pd.DataFrame({"hdd_eurostat": es, "hdd_model": ours.round(0)}).dropna()
    out["ratio"] = (out["hdd_model"] / out["hdd_eurostat"]).round(3)
    return out.reset_index(names="year")


# ==========================================================================
# 4. Climatologia e dimensionamento del futuro 100% rinnovabile
# ==========================================================================
def climatology(h):
    m = h.groupby(h.index.month)[["cf_wind", "cf_solar", "t2m", "demand_gw"]].mean()
    m.index.name = "month"
    winter = h[h.index.month.isin([11, 12, 1, 2])][["cf_wind", "cf_solar", "t2m", "demand_gw"]].mean()
    m.loc["winter_NDJF"] = winter
    m.loc["year"] = h[["cf_wind", "cf_solar", "t2m", "demand_gw"]].mean()
    return m


def sizing(h):
    annual_mwh = C.ANNUAL_DEMAND_TWH * 1e6 * C.OVERBUILD
    w_mwh_per_turbine = C.P_TURBINE_MW * h["cf_wind"].mean() * 8760
    s_mwh_per_panel = C.P_PANEL_KW / 1000 * h["cf_solar"].mean() * 8760
    N = annual_mwh * C.SHARE_WIND_ENERGY / w_mwh_per_turbine
    M = annual_mwh * C.SHARE_SOLAR_ENERGY / s_mwh_per_panel
    return pd.DataFrame([{
        "N_turbines": round(N), "wind_capacity_GW": round(N * C.P_TURBINE_MW / 1e3, 1),
        "M_panels": round(M), "solar_capacity_GW": round(M * C.P_PANEL_KW / 1e6, 1),
        "cf_wind_mean": round(h["cf_wind"].mean(), 3), "cf_solar_mean": round(h["cf_solar"].mean(), 3),
    }])


# ==========================================================================
# 5. Rilevamento delle Dunkelflaute storiche -> parametri di scenario
# ==========================================================================
def combined_cf(h, sz):
    gw_w, gw_s = sz["wind_capacity_GW"].iloc[0], sz["solar_capacity_GW"].iloc[0]
    return (gw_w * h["cf_wind"] + gw_s * h["cf_solar"]) / (gw_w + gw_s)


def merge_short_gaps(flag, gap):
    """Riempie le pause (False) più corte di `gap` ore comprese tra due tratti True."""
    vals = flag.to_numpy().copy()
    grp = (flag != flag.shift()).cumsum()
    runs = list(zip(flag.groupby(grp).first(), flag.groupby(grp).size()))
    pos = 0
    for i, (v, n) in enumerate(runs):
        if not v and 0 < i < len(runs) - 1 and n <= gap:
            vals[pos:pos + n] = True
        pos += n
    return pd.Series(vals, index=flag.index)


def detect_events(h, sz, clim):
    cf = combined_cf(h, sz)
    roll = cf.rolling(C.DF_WINDOW_H, center=True, min_periods=C.DF_WINDOW_H // 2).mean()
    flag = roll < C.DF_THRESHOLD * cf.mean()

    # fondi eventi separati da pause brevi, poi raggruppa le ore consecutive
    flag = merge_short_gaps(flag, C.DF_MERGE_GAP_H)
    grp = (flag != flag.shift()).cumsum()

    # temperatura "normale" per giorno dell'anno, per calcolare ΔT
    t_clim = h["t2m"].groupby(h.index.dayofyear).mean().rolling(15, center=True, min_periods=1).mean()
    month_cf = h.groupby(h.index.month)[["cf_wind", "cf_solar"]].mean()

    rows = []
    for _, seg in h[flag].groupby(grp[flag]):
        dur = len(seg)
        if dur < C.DF_MIN_DURATION_H:
            continue
        m = seg.index.month
        ref_w = month_cf.loc[m, "cf_wind"].values.mean()
        ref_s = month_cf.loc[m, "cf_solar"].values.mean()
        t_norm = t_clim.loc[seg.index.dayofyear].values.mean()
        rows.append({
            "start": seg.index[0], "end": seg.index[-1], "duration_h": dur,
            "cf_wind_mean": round(seg["cf_wind"].mean(), 3),
            "cf_solar_mean": round(seg["cf_solar"].mean(), 3),
            "delta_wind_pct": round(100 * (1 - seg["cf_wind"].mean() / ref_w), 1),   # δ_eol
            "delta_solar_pct": round(100 * (1 - seg["cf_solar"].mean() / ref_s), 1), # δ_sol
            "t2m_mean": round(seg["t2m"].mean(), 1),
            "delta_t": round(seg["t2m"].mean() - t_norm, 1),                         # ΔT
            "demand_mean_gw": round(seg["demand_gw"].mean(), 1),
            "min_cf_48h": round(roll.loc[seg.index].min(), 3),
        })
    ev = pd.DataFrame(rows)
    if ev.empty:
        return ev
    # gravità = durata x profondità, e tempo di ritorno empirico della durata
    ev["severity"] = (ev["duration_h"] * (1 - ev["min_cf_48h"] / cf.mean())).round(1)
    n_years = h.index.year.nunique()
    ev = ev.sort_values("duration_h", ascending=False).reset_index(drop=True)
    ev["return_period_yr"] = (n_years / (ev.index + 1)).round(1)   # stima empirica, rozza nella coda
    return ev


# ==========================================================================
# 6. Previsione ensemble -> probabilità di Dunkelflaute nei prossimi giorni
# ==========================================================================
def forecast_summary(sz, clim, calib):
    runs = sorted(glob.glob(str(C.RAW / "ensemble" / "*")))
    if not runs:
        return None
    run = runs[-1]
    wind_w = {p[0]: p[3] for p in C.POINTS}; sol_w = {p[0]: p[4] for p in C.POINTS}
    sw, ss = sum(wind_w.values()), sum(sol_w.values())
    pv_k = calib.set_index("point")["pv_scale"].to_dict()   # stessa taratura PVGIS dello storico
    cfw, cfs = {}, {}
    for f in glob.glob(f"{run}/*.csv"):
        name = f.split("/")[-1][:-4]
        d = pd.read_csv(f, parse_dates=["time"]).set_index("time")
        for col in d.columns:
            mm = re.match(r"wind_speed_100m(?:_(member\d+))?$", col)
            if mm:
                key = mm.group(1) or "control"
                ghi_col = col.replace("wind_speed_100m", "shortwave_radiation")
                t_col = col.replace("wind_speed_100m", "temperature_2m")
                cw = pd.Series(wind_cf(d[col]), index=d.index) * wind_w[name] / sw
                cs = (pd.Series(solar_cf(d[ghi_col], d[t_col]), index=d.index) * pv_k.get(name, 1.0)).clip(upper=1) * sol_w[name] / ss
                cfw[key] = cfw.get(key, 0) + cw
                cfs[key] = cfs.get(key, 0) + cs
    gw_w, gw_s = sz["wind_capacity_GW"].iloc[0], sz["solar_capacity_GW"].iloc[0]
    hist_mean = (gw_w * clim.loc["year", "cf_wind"] + gw_s * clim.loc["year", "cf_solar"]) / (gw_w + gw_s)
    members = pd.DataFrame({k: (gw_w * cfw[k] + gw_s * cfs[k]) / (gw_w + gw_s) for k in cfw}).dropna()
    roll = members.rolling(C.DF_WINDOW_H, center=True, min_periods=C.DF_WINDOW_H // 2).mean()
    in_df = roll < C.DF_THRESHOLD * hist_mean
    daily = pd.DataFrame({
        "p_dunkelflaute": in_df.resample("D").max().mean(axis=1).round(2),   # quota di membri in evento
        "cf_p10": members.resample("D").mean().quantile(0.1, axis=1).round(3),
        "cf_median": members.resample("D").mean().median(axis=1).round(3),
        "cf_p90": members.resample("D").mean().quantile(0.9, axis=1).round(3),
    })
    daily["days_ahead"] = range(len(daily))
    return daily


# ==========================================================================
if __name__ == "__main__":
    h, calib = build_country()
    h = add_demand(h)
    clim = climatology(h)
    sz = sizing(h)
    ev = detect_events(h, sz, clim)
    hdd = eurostat_hdd_check(h)

    h.round(4).to_csv(C.PROC / "hourly_country.csv")
    clim.round(4).to_csv(C.PROC / "climatology.csv")
    sz.to_csv(C.PROC / "sizing.csv", index=False)
    ev.to_csv(C.PROC / "events.csv", index=False)
    calib.to_csv(C.PROC / "calibration.csv", index=False)
    if not hdd.empty:
        hdd.to_csv(C.PROC / "calibration_hdd.csv", index=False)

    fc = forecast_summary(sz, clim, calib)
    if fc is not None:
        fc.to_csv(C.PROC / "forecast_summary.csv")

    print("\n== Dimensionamento futuro 100% rinnovabile ==\n", sz.to_string(index=False))
    print("\n== Taratura solare (PVGIS) ==\n", calib.to_string(index=False))
    if not hdd.empty:
        print("\n== Gradi giorno: modello vs Eurostat ==\n", hdd.tail(5).to_string(index=False))
    print(f"\n== {len(ev)} Dunkelflaute trovate; le 10 più lunghe ==")
    if not ev.empty:
        print(ev.head(10)[["start", "duration_h", "delta_wind_pct", "delta_solar_pct", "delta_t", "return_period_yr"]].to_string(index=False))
    if fc is not None:
        print("\n== Previsione: probabilità di Dunkelflaute per giorno ==\n", fc.to_string())
