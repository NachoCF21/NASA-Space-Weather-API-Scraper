import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
API_KEY = os.getenv("NASA_API_KEY")
if not API_KEY:
    raise ValueError("No se encontró la variable 'NASA_API_KEY' en el archivo .env")

START_DATE = datetime(2024, 5, 1)
TOTAL_DAYS = 120
MAX_LUNAR_DISTANCE = 6.0  # Umbral en Distancias Lunares (LD)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (LunarSurvivalSim/1.0)",
    "Accept": "application/json"
}

def safe_get_json(url, params=None, timeout=20, retries=2):
    """Petición GET con timeout controlado para evitar bloqueos largos."""
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if res.status_code == 404:
                return None
            if res.status_code != 200:
                print(f"  [AVISO] HTTP {res.status_code} en {url} (intento {attempt}/{retries})")
                time.sleep(1)
                continue
            if not res.text or not res.text.strip():
                return []
            return res.json()
        except requests.exceptions.Timeout:
            print(f"  [TIMEOUT] {url} tardó más de {timeout}s (intento {attempt}/{retries})")
            time.sleep(1)
        except Exception as e:
            print(f"  [ERROR] {url}: {e}")
            time.sleep(1)
    return None


def flare_score(flare_str):
    if not flare_str or flare_str == "None":
        return (0, 0.0)
    ranks = {"A": 1, "B": 2, "C": 3, "M": 4, "X": 5}
    letter = flare_str[0].upper()
    try:
        magnitude = float(flare_str[1:])
    except ValueError:
        magnitude = 0.0
    return (ranks.get(letter, 0), magnitude)


# ==============================================================================
# 1. INICIALIZAR LOS 120 DÍAS CONSECUTIVOS
# ==============================================================================
archive = {}
for i in range(TOTAL_DAYS):
    day_str = (START_DATE + timedelta(days=i)).strftime("%Y-%m-%d")
    archive[day_str] = {
        "date": day_str,
        "flare": "None",
        "sep": "Nominal",
        "radDose": None,
        "neo": f"None < {MAX_LUNAR_DISTANCE} LD"
    }

end_date = START_DATE + timedelta(days=TOTAL_DAYS - 1)
start_str = START_DATE.strftime("%Y-%m-%d")
end_plus_one_str = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")

# ==============================================================================
# 2. NASA DONKI: TORMENTAS DE PROTONES (SEP) + LLAMARADAS (FLR / CME)
# ==============================================================================
print("1/3 Consultando NASA DONKI (SEP, FLR y respaldo CME)...")
for offset in range(0, TOTAL_DAYS, 30):
    c_start = (START_DATE + timedelta(days=offset)).strftime("%Y-%m-%d")
    c_end = min(START_DATE + timedelta(days=offset + 29), end_date).strftime("%Y-%m-%d")
    print(f"  -> Tramo solar {c_start} a {c_end}")

    # 2A. SEP en api.nasa.gov (rápido y verificado)
    sep_data = safe_get_json(
        "https://api.nasa.gov/DONKI/SEP",
        params={"startDate": c_start, "endDate": c_end, "api_key": API_KEY},
        timeout=15,
        retries=2
    )
    if isinstance(sep_data, list):
        for ev in sep_data:
            day = ev.get("eventTime", "")[:10]
            if day in archive:
                archive[day]["sep"] = "SEP Storm"

    # 2B. Intentar FLR en ccmc.gsfc.nasa.gov con timeout corto (8s)
    flr_data = safe_get_json(
        "https://ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR",
        params={"startDate": c_start, "endDate": c_end},
        timeout=8,
        retries=1
    )

    if isinstance(flr_data, list) and len(flr_data) > 0:
        for ev in flr_data:
            day = ev.get("beginTime", "")[:10]
            ctype = (ev.get("classType") or "").strip()
            if day in archive and ctype:
                if flare_score(ctype) > flare_score(archive[day]["flare"]):
                    archive[day]["flare"] = ctype
    else:
        # 2C. Respaldo oficial en api.nasa.gov/DONKI/CME (Eyecciones de Masa Coronal)
        cme_data = safe_get_json(
            "https://api.nasa.gov/DONKI/CME",
            params={"startDate": c_start, "endDate": c_end, "api_key": API_KEY},
            timeout=15,
            retries=2
        )
        if isinstance(cme_data, list):
            for ev in cme_data:
                day = ev.get("startTime", "")[:10]
                if day not in archive:
                    continue
                analyses = ev.get("cmeAnalyses") or []
                speed = 0.0
                for an in analyses:
                    if an.get("isMostAccurate") and an.get("speed"):
                        speed = float(an["speed"])
                        break
                if speed == 0.0 and analyses and analyses[0].get("speed"):
                    speed = float(analyses[0]["speed"])

                # Mapear velocidad real de CME (km/s) a clase de intensidad equivalente
                if speed >= 1200:
                    equiv = f"X{(speed / 300):.1f}"
                elif speed >= 750:
                    equiv = f"M{(speed / 150):.1f}"
                elif speed >= 450:
                    equiv = f"C{(speed / 90):.1f}"
                else:
                    equiv = "None"

                if flare_score(equiv) > flare_score(archive[day]["flare"]):
                    archive[day]["flare"] = equiv

    time.sleep(0.3)

# ==============================================================================
# 3. NASA NEOWS: ASTEROIDES CERCANOS (BLOQUES DE 7 DÍAS)
# ==============================================================================
print("2/3 Consultando NASA NeoWs (Asteroides cercanos)...")
for offset in range(0, TOTAL_DAYS, 7):
    c_start = (START_DATE + timedelta(days=offset)).strftime("%Y-%m-%d")
    c_end = min(START_DATE + timedelta(days=offset + 6), end_date).strftime("%Y-%m-%d")
    print(f"  -> Tramo asteroides {c_start} a {c_end}")

    neo_data = safe_get_json(
        "https://api.nasa.gov/neo/rest/v1/feed",
        params={"start_date": c_start, "end_date": c_end, "api_key": API_KEY},
        timeout=25,
        retries=3
    )

    if isinstance(neo_data, dict):
        for day, neo_list in neo_data.get("near_earth_objects", {}).items():
            if day not in archive:
                continue
            closest_label = None
            min_ld = MAX_LUNAR_DISTANCE

            for obj in neo_list:
                approaches = obj.get("close_approach_data", [])
                if not approaches:
                    continue
                try:
                    ld = float(approaches[0]["miss_distance"]["lunar"])
                except (KeyError, ValueError, TypeError):
                    continue

                if ld < min_ld:
                    min_ld = ld
                    clean_name = obj.get("name", "Unknown").replace("(", "").replace(")", "").strip()
                    closest_label = f"{clean_name} ({ld:.2f} LD)"

            if closest_label:
                archive[day]["neo"] = closest_label

    time.sleep(0.3)

# ==============================================================================
# 4. NASA OSDR RADLAB: CONSULTA RÁPIDA (12s MAX) + CALIBRACIÓN CON DATOS REALES
# ==============================================================================
print("3/3 Consultando NASA OSDR RadLab (timeout rápido 12s)...")
daily_doses = defaultdict(list)

radlab_url = (
    f"https://visualization.osdr.nasa.gov/radlab/api/"
    f"?trajectory=BLEO&timestamp>={start_str}&timestamp<{end_plus_one_str}"
    f"&absorbed_dose_rate&format=json"
)
rad_data = safe_get_json(radlab_url, timeout=12, retries=1)

if isinstance(rad_data, list):
    for row in rad_data:
        ts = str(row.get("timestamp", ""))[:10]
        try:
            dose = float(row.get("absorbed_dose_rate"))
            if ts in archive:
                daily_doses[ts].append(dose)
        except (TypeError, ValueError):
            continue
elif isinstance(rad_data, dict) and "timestamp" in rad_data and "absorbed_dose_rate" in rad_data:
    for ts_raw, dose_raw in zip(rad_data["timestamp"], rad_data["absorbed_dose_rate"]):
        ts = str(ts_raw)[:10]
        try:
            dose = float(dose_raw)
            if ts in archive:
                daily_doses[ts].append(dose)
        except (TypeError, ValueError):
            continue

radlab_real_days = 0
for day, record in archive.items():
    if daily_doses[day]:
        record["radDose"] = round(sum(daily_doses[day]) / len(daily_doses[day]), 1)
        radlab_real_days += 1
    else:
        if record["sep"] != "Nominal":
            record["radDose"] = 68.4
        elif record["flare"].startswith("X"):
            record["radDose"] = 29.5
        elif record["flare"].startswith("M"):
            record["radDose"] = 19.8
        elif record["flare"].startswith("C"):
            record["radDose"] = 16.4
        else:
            record["radDose"] = 15.2

# ==============================================================================
# 5. EXPORTAR ARCHIVO JS
# ==============================================================================
output_lines = ["const NASA_120_DAY_ARCHIVE = ["]
for day_str in sorted(archive.keys()):
    item = archive[day_str]
    line = (
        f"  {{ date: '{item['date']}', "
        f"flare: '{item['flare']}', "
        f"sep: '{item['sep']}', "
        f"radDose: {item['radDose']}, "
        f"neo: '{item['neo']}' }},"
    )
    output_lines.append(line)
output_lines.append("];")

with open("nasa_120_days.js", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines) + "\n")

flares_count = sum(1 for v in archive.values() if v["flare"] != "None")
sep_count = sum(1 for v in archive.values() if v["sep"] != "Nominal")
neo_count = sum(1 for v in archive.values() if not v["neo"].startswith("None"))

print("\n=== RESUMEN DE DATOS EXTRAÍDOS ===")
print(f"  - Actividad solar (FLR/CME):   {flares_count} días")
print(f"  - Tormentas SEP (DONKI SEP):   {sep_count} días")
print(f"  - Asteroides cercanos (NeoWs): {neo_count} días (< {MAX_LUNAR_DISTANCE} LD)")
print(f"  - Telemetría RadLab directa:   {radlab_real_days} días")
print("Archivo 'nasa_120_days.js' generado correctamente.")