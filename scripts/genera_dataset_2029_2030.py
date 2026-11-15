"""
Genera simulazione_dunkelflaute_nov2029_gen2030.csv a partire da hourly_country.csv.

Periodo: 2029-11-01 00:00 -> 2030-01-31 23:00 (2208 ore).
Evento Dunkelflaute imposto: 72 h in cui CF_comb = 0,2 x baseline climatologica (-80%).
"""
import sys
import numpy as np
import pandas as pd
from scipy.stats import norm

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "simulazione_dunkelflaute_nov2029_gen2030.csv"
SEED = 42
rng = np.random.default_rng(SEED)

# ---------------- Parametri di scenario ----------------
C_TOT = 439.0                       # GW installati eolico+FV (sistema "precedente" del progetto)
W_EOL, W_SOL = 0.65, 0.35           # proporzione di capacità richiesta
C_EOL, C_SOL = C_TOT * W_EOL, C_TOT * W_SOL
F_MAX = 40.0                        # GW programmabili di riserva (gas ~35 GW + biomassa, ordine di grandezza DE 2030)
QUOTA_NEC = 0.65                    # consumi necessari / totali

# Crescita della domanda 2030 vs storico, per fascia oraria (media ~ +12%)
#  notte: ricarica EV notturna + pompe di calore; sera: rientro a casa + ricarica EV
def crescita(h):
    if h < 6:   return 0.14   # notte 00-06
    if h < 12:  return 0.10   # mattina 06-12
    if h < 18:  return 0.09   # pomeriggio 12-18
    return 0.15               # sera 18-24

EV_START = pd.Timestamp("2029-12-10 06:00")   # inizio nucleo evento (lunedì)
EV_LEN = 72                                    # ore di nucleo
RAMP = 18                                      # ore di rampa prima/dopo
DROP = 0.80                                    # -80% rispetto alla baseline

# ---------------- Storico ----------------
h = pd.read_csv(SRC, parse_dates=["time"])
h["doy"] = h.time.dt.dayofyear
h["hour"] = h.time.dt.hour
h["md"] = h.time.dt.strftime("%m-%d")
h["dow"] = h.time.dt.dayofweek
FESTIVI = {"12-24", "12-25", "12-26", "12-31", "01-01"}
def tipo_giorno(md, dow):
    if md in FESTIVI: return "F_" + md
    return "sab" if dow == 5 else ("dom" if dow == 6 else "fer")
h["tipo"] = [tipo_giorno(m, d) for m, d in zip(h.md, h.dow)]

# Asse dei tempi simulato
ts = pd.date_range("2029-11-01 00:00", "2030-01-31 23:00", freq="h")
sim = pd.DataFrame({"timestamp": ts})
sim["doy"] = ts.dayofyear
sim["hour"] = ts.hour
sim["md"] = ts.strftime("%m-%d")
sim["tipo"] = [tipo_giorno(m, d) for m, d in zip(sim.md, ts.dayofweek)]

def doy_dist(a, b):
    d = np.abs(a - b)
    return np.minimum(d, 365 - d)

# ---------------- Baseline climatologica CF (media 2010-2025, finestra +-7 gg, stessa ora) ----------------
cf_w_base, cf_s_base = np.empty(len(sim)), np.empty(len(sim))
for i, (doy, hr) in enumerate(zip(sim.doy, sim.hour)):
    m = (h.hour == hr) & (doy_dist(h.doy.values, doy) <= 7)
    cf_w_base[i] = h.loc[m, "cf_wind"].mean()
    cf_s_base[i] = h.loc[m, "cf_solar"].mean()
sim["cf_w_base"], sim["cf_s_base"] = cf_w_base, cf_s_base
sim["cf_comb_base"] = W_EOL * cf_w_base + W_SOL * cf_s_base

# ---------------- Serie meteo di partenza: inverno analogo reale senza Dunkelflaute propria ----------------
def ha_evento(cf_w, cf_s):
    cf24 = pd.Series(W_EOL * cf_w + W_SOL * cf_s).rolling(24, center=True, min_periods=12).mean()
    run, best = 0, 0
    for v in (cf24 < 0.06):
        run = run + 1 if v else 0
        best = max(best, run)
    return best >= 48

candidati = {}
for y in range(2010, 2025):
    blk = h[(h.time >= f"{y}-11-01") & (h.time < f"{y+1}-02-01")]
    if len(blk) != 2208:
        continue
    cfc_y = W_EOL * blk.cf_wind.values + W_SOL * blk.cf_solar.values
    # rapporto minimo (media mobile 72 h) tra CF_comb dell'anno e baseline climatologica
    r72 = (pd.Series(cfc_y).rolling(72).mean() / pd.Series(sim.cf_comb_base.values).rolling(72).mean()).min()
    candidati[y] = round(float(r72), 3)
# inverno analogo = quello il cui peggior periodo naturale di 72 h e' il piu' lieve
anno = max(candidati, key=candidati.get)
blk = h[(h.time >= f"{anno}-11-01") & (h.time < f"{anno+1}-02-01")].reset_index(drop=True)
# Perturbazione moltiplicativa AR(1) (sigma 8%, persistenza ~1 giorno) per non copiare l'anno storico
def ar1(n, phi, sigma):
    z = np.zeros(n); e = rng.normal(0, sigma * np.sqrt(1 - phi**2), n)
    for t in range(1, n): z[t] = phi * z[t-1] + e[t]
    return z
cf_w = np.clip(blk.cf_wind.values * np.exp(ar1(len(sim), 0.96, 0.08)), 0, 0.95)
cf_s = np.clip(blk.cf_solar.values * np.exp(ar1(len(sim), 0.90, 0.05)), 0, 0.95)

# ---------------- Evento Dunkelflaute imposto ----------------
i0 = int((EV_START - ts[0]) / pd.Timedelta("1h"))
i1 = i0 + EV_LEN
core = np.zeros(len(sim), bool); core[i0:i1] = True
target_w = (1 - DROP) * cf_w_base
target_s = (1 - DROP) * cf_s_base
# piccola variabilità interna (+-10%) poi riscalata: media sul nucleo esattamente -80%
noise = np.exp(ar1(EV_LEN, 0.9, 0.10))
tw = target_w[i0:i1] * noise
ts_ = target_s[i0:i1] * noise
k = ((1 - DROP) * sim.cf_comb_base.values[i0:i1].sum()) / (W_EOL * tw + W_SOL * ts_).sum()
cf_w[i0:i1], cf_s[i0:i1] = tw * k, ts_ * k
# rampe di ingresso/uscita (interpolazione lineare tra serie analoga e serie d'evento)
for j in range(1, RAMP + 1):
    a = j / (RAMP + 1)                       # peso della serie normale
    for idx in (i0 - j, i1 - 1 + j):
        cf_w[idx] = a * cf_w[idx] + (1 - a) * target_w[idx]
        cf_s[idx] = a * cf_s[idx] + (1 - a) * target_s[idx]

# ---------------- Domanda: estrazione dalla distribuzione empirica condizionata ----------------
# Per ogni ora: distribuzione storica di demand_gw a parità di ora, tipo di giorno, data +-7 gg
# (festivi: stessa data). Valore = quantile della distribuzione a un livello u(t) correlato nel tempo.
z = ar1(len(sim), 0.97, 1.0)
z = z / z.std()
# durante l'evento (anticiclone freddo) la domanda si sposta verso la coda alta
shift = np.zeros(len(sim)); shift[i0 - RAMP:i1 + RAMP] = 0.6; shift[core] = 1.0
u = norm.cdf(z + shift)

grp = {k: g for k, g in h.groupby(["hour", "tipo"])}
dem = np.empty(len(sim))
for i, (doy, hr, tp, md) in enumerate(zip(sim.doy, sim.hour, sim.tipo, sim.md)):
    if tp.startswith("F_"):
        vals = h.loc[(h.hour == hr) & (h.md == md), "demand_gw"].values
    else:
        g = grp[(hr, tp)]
        vals = g.loc[doy_dist(g.doy.values, doy) <= 7, "demand_gw"].values
    dem[i] = np.quantile(vals, u[i]) * (1 + crescita(hr))

# ---------------- Bilancio orario ----------------
p_eol = C_EOL * cf_w
p_sol = C_SOL * cf_s
res = p_eol + p_sol
deficit = np.maximum(dem - res, 0)
fossile = np.minimum(deficit, F_MAX)
out = pd.DataFrame({
    "tempo_ore": np.arange(len(sim)),
    "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
    "potenza_consumata": dem,
    "potenza_consumata_necessaria": QUOTA_NEC * dem,
    "potenza_consumata_non_essenziale": (1 - QUOTA_NEC) * dem,
    "potenza_generata_solare": p_sol,
    "potenza_generata_eolica": p_eol,
    "potenza_generata_non_rinnovabili": fossile,
    "scarto": np.maximum(res - dem, 0),
    "potenza_non_servita": deficit - fossile,
    "dunkelflaute": core.astype(int),
}).round(3)
out.to_csv(OUT, index=False)

# ---------------- Controlli ----------------
cfc = W_EOL * cf_w + W_SOL * cf_s
print("anno analogo:", anno, "| peggior 72h/baseline per anno:", candidati)
print("evento:", ts[i0], "->", ts[i1 - 1])
print("CF_comb nucleo / baseline:", cfc[core].mean() / sim.cf_comb_base.values[core].mean())
print("CF_comb medio fuori evento:", cfc[~core].mean(), "| baseline:", sim.cf_comb_base.values[~core].mean())
print(out.drop(columns=["timestamp"]).describe().T.round(2))
for lab, m in [("evento", core), ("fuori evento", ~core)]:
    o = out[m]
    print(f"\n{lab}: domanda {o.potenza_consumata.mean():.1f} GW | FV {o.potenza_generata_solare.mean():.1f} | "
          f"eolico {o.potenza_generata_eolica.mean():.1f} | fossile {o.potenza_generata_non_rinnovabili.mean():.1f} | "
          f"non servita {o.potenza_non_servita.mean():.1f} GW ({o.potenza_non_servita.sum():.0f} GWh) | scarto {o.scarto.sum():.0f} GWh")
storico = h[h.time.dt.month.isin([11, 12, 1])].demand_gw.mean()
print("\ncrescita domanda effettiva vs storico nov-gen:", dem.mean() / storico - 1)
