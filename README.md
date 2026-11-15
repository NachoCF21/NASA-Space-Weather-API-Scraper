# 🛰️ NASA Space Weather API Scraper

**NASA Space Weather API Scraper** (`nasa_space_weather.py`) is a Python data-collection pipeline that queries official NASA open APIs to build a 120-day space weather and near-Earth object telemetry dataset starting from `2024-05-01`. Designed to feed the **LUNAR BASE 30: Artemis IV & Orion Survival Simulator** ([Game Repository](PASTE_GAME_REPO_URL_HERE)), the script aggregates daily records of solar flares, solar energetic proton (SEP) storms, close-approach asteroids, and radiation dose rates, exporting them directly into a ready-to-use JavaScript archive (`nasa_120_days.js`).

---

## 📡 NASA APIs & Telemetry Pipeline

The script processes 120 consecutive days using controlled HTTP timeouts, automatic retries, and fallback logic to prevent rate-limiting or endpoint stalls:

- **☀️ NASA DONKI — Solar Flares & Proton Storms (30-day chunks):**
  - Queries `api.nasa.gov/DONKI/SEP` to detect Solar Energetic Proton storms (`SEP Storm` vs. `Nominal`).
  - Queries `ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR` (8s timeout) to log the strongest daily solar flare class (`A`, `B`, `C`, `M`, or `X`).
  - Falls back to `api.nasa.gov/DONKI/CME` if flare data is unavailable, mapping real Coronal Mass Ejection speeds (`km/s`) into equivalent flare intensity tiers (`X` for `≥ 1200 km/s`, `M` for `≥ 750 km/s`, `C` for `≥ 450 km/s`).
- **☄️ NASA NeoWs — Near-Earth Objects (7-day chunks):**
  - Queries `api.nasa.gov/neo/rest/v1/feed` to track asteroids passing closer than `6.0` Lunar Distances (`LD`), recording the closest object's name and miss distance per day.
- **☢️ NASA OSDR RadLab — Radiation Dose Rates:**
  - Queries `visualization.osdr.nasa.gov/radlab/api/` (`BLEO` trajectory, 12s timeout) to calculate daily average absorbed radiation dose rates in `µGy/h`.
  - Applies calibrated baseline values (`68.4 µGy/h` for SEP storms, `29.5` for X-class, `19.8` for M-class, `16.4` for C-class, and `15.2` nominal) on days without direct RadLab readings.

---

## ⚙️ Setup & Usage

1. **Install dependencies:**
   ```bash
   pip install requests python-dotenv
   ```
2. **Configure your NASA API key:** Create a `.env` file in the root directory and add your free key from [api.nasa.gov](https://api.nasa.gov/):
   ```env
   NASA_API_KEY=your_nasa_api_key_here
   ```
3. **Run the scraper:**
   ```bash
   python nasa_space_weather.py
   ```
4. **Integrate with the game:** Copy the generated `nasa_120_days.js` file into the simulator's `data/` folder.

---

## 📦 Output Format (`nasa_120_days.js`)

The script exports a JavaScript array named `NASA_120_DAY_ARCHIVE` containing 120 chronological objects:

```javascript
const NASA_120_DAY_ARCHIVE = [
  { date: '2024-05-01', flare: 'M1.9', sep: 'Nominal', radDose: 19.8, neo: 'None < 6.0 LD' },
  { date: '2024-05-04', flare: 'C8.1', sep: 'Nominal', radDose: 19.0, neo: '2024 JQ1 (4.80 LD)' },
  // ... 120 days total
];
```
```
