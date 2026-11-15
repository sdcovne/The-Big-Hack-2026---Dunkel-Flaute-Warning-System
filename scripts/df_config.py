"""
Configurazione del toy model Dunkelflaute.
Modifica qui paese, punti rappresentativi, anni e ipotesi tecniche.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Cartelle
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent   # radice del repository (gli script stanno in scripts/)
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

# --------------------------------------------------------------------------
# Paese e punti rappresentativi
# --------------------------------------------------------------------------
# Per un toy model non serve una griglia: bastano pochi punti pesati.
# I pesi "wind" e "solar" dicono quanta capacità installata c'è in quell'area
# (eolico concentrato al nord e offshore, solare al sud). Sommano a 1 ciascuno.
COUNTRY = "DE"            # codice Eurostat (DE, IT, FR, ...)
POINTS = [
    # nome,                 lat,   lon,   peso_eolico, peso_solare, peso_domanda
    ("SchleswigHolstein",  54.40,  9.60,  0.25,        0.03,        0.05),
    ("NiedersachsenCoast", 53.30,  7.90,  0.25,        0.07,        0.10),
    ("Mecklenburg",        53.80, 12.30,  0.15,        0.05,        0.03),
    ("Brandenburg",        52.50, 13.60,  0.20,        0.10,        0.12),
    ("NRW",                51.40,  7.30,  0.05,        0.15,        0.30),
    ("Bayern",             48.60, 11.50,  0.05,        0.35,        0.22),
    ("BadenWuerttemberg",  48.60,  9.00,  0.05,        0.25,        0.18),
]

# --------------------------------------------------------------------------
# Periodo storico
# --------------------------------------------------------------------------
YEAR_START = 2010
YEAR_END = 2025           # incluso

# --------------------------------------------------------------------------
# Ipotesi tecniche (parametri del toy model)
# --------------------------------------------------------------------------
# Eolico: curva di potenza semplificata di una turbina onshore moderna
WIND_CUT_IN = 3.0         # m/s
WIND_RATED = 12.0         # m/s
WIND_CUT_OUT = 25.0       # m/s
WIND_LOSSES = 0.88        # scie, disponibilità, perdite elettriche
P_TURBINE_MW = 5.0        # potenza di una pala

# Solare
PV_GAMMA = -0.004         # coefficiente di temperatura (1/°C)
PV_NOCT_DELTA = 25.0      # riscaldamento della cella a 800 W/m² (°C)
PV_PR = 0.86              # performance ratio (perdite di sistema)
P_PANEL_KW = 0.4          # potenza di un pannello

# Domanda
HDD_BASE = 18.0           # gradi giorno Eurostat: base 18 °C ...
HDD_THRESHOLD = 15.0      # ... conteggiati solo se T media giornaliera <= 15 °C
ANNUAL_DEMAND_TWH = 500.0 # consumo elettrico annuo (ipotesi di scenario; controlla il valore attuale su Eurostat)
HEAT_SENSITIVITY_K = 0.012  # +1,2% di domanda per ogni grado giorno (ipotesi da tarare)
ALPHA_ESSENTIAL = 0.65    # quota di consumi necessari (ipotesi di scenario)

# Mix futuro (in capacità installata) per dimensionare N e M
SHARE_WIND_ENERGY = 0.60  # quota di energia annua attesa dall'eolico
SHARE_SOLAR_ENERGY = 0.40 # quota di energia annua attesa dal solare
OVERBUILD = 1.15          # margine di sovra-dimensionamento sul consumo annuo

# Rilevamento Dunkelflaute
DF_WINDOW_H = 48          # finestra della media mobile
DF_THRESHOLD = 0.4    # evento se CF combinato < 40% della media di lungo periodo
DF_MIN_DURATION_H = 24    # durata minima per considerarlo un evento
DF_MERGE_GAP_H = 6        # unisce eventi separati da pause brevi

# Previsione ensemble
ENSEMBLE_MODEL = "ecmwf_ifs025"   # 51 membri, ~15 giorni
FORECAST_DAYS = 15
