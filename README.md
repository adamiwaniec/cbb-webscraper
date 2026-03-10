# CBB WebScraper

A Python web scraper for collecting NCAA Division 1 men's college basketball game data and betting odds from multiple sources.

**Data sources:**
- **ESPN** (via CBBpy) — game info, team stats, boxscores, play-by-play (historical from 2003 + upcoming)
- **BetIQ** (via Selenium) — historical sportsbook betting lines (moneyline, spread, total)
- **OddsPortal** (via OddsHarvester) — historical and upcoming betting odds (moneyline, spread, total) with line movement


## Installation

### Requirements

- Python 3.9+
- Google Chrome + [ChromeDriver](https://chromedriver.chromium.org/downloads) (must match your Chrome version — required for BetIQ scraping)
- CUDA-compatible GPU optional but not required

### Python packages

```bash
pip install pandas numpy aiohttp selenium webdriver-manager
```

### CBBpy (custom fork)

Install from the local clone included in this project:

```bash
pip install ../CBBpy
```

Or from GitHub:

```bash
pip install git+https://github.com/adamiwaniec/CBBpy.git
```

### OddsHarvester

Install from the local clone included in this project:

```bash
pip install ../OddsHarvester
```

Or from GitHub:

```bash
pip install git+https://github.com/jordantete/OddsHarvester.git
```


## Configuration

All file paths and output locations are configured in `config.py`. You generally do not need to edit this file.

Scraping behavior is configured via macros at the top of each script (`scrape_main.py`, `scrape_odds.py`).


## Usage

### Scraping ESPN game data (`scrape_main.py`)

Edit the configuration macros at the top of `scrape_main.py`:

```python
SCRAPE_MODE = 'GAME_INFO'   # 'GAME_INFO', 'GAME_STATS', 'BOXSCORES', or 'PBP'
START_YEAR = 2021
END_YEAR = 2026
USE_EXISTING_GAME_IDS = True   # Reuse previously fetched game ID list (faster)
```

Run the scraper:

```bash
python scrape_main.py
```

Run once per mode to populate all four datasets. **PBP mode** generates a ~4.5 GB file and takes several hours.

Data is saved to `../data/cbb_data_raw/`.

**Output files:**
- `game_info.csv` (~29 MB) — game metadata: game_id, teams, scores, dates, rankings, spreads
- `game_stats.csv` (~20 MB) — team-level stats: FG%, 3P%, FT%, rebounds, assists, steals, blocks, turnovers
- `boxscore_data.csv` (~240 MB) — player-level stats: minutes, shooting, rebounds, assists, fouls
- `pbp_data.csv` (~4.5 GB) — play-by-play: field goals, free throws, fouls, etc.

### Scraping betting odds (`scrape_odds.py`)

`scrape_odds.py` handles three scraping modes, all configurable via macros at the top of the file.

#### BetIQ historical lines (Selenium)

Requires ChromeDriver. Configure:

```python
BETIQ_ENABLED = True
MIN_SEASON = 2015
MAX_SEASON = 2025
HEADLESS_MODE = True   # Set False to see browser
```

#### OddsHarvester historical odds (async)

```python
OH_HISTORICAL_ENABLED = True
OH_HISTORICAL_SEASONS = [2022, 2023, 2024, 2025]
OH_ALL_MARKETS = True   # Scrape moneyline, spread, and total
```

Note: OddsHarvester scrapes OddsPortal asynchronously. Historical scraping can take a long time for many seasons.

#### OddsHarvester upcoming odds

Upcoming odds are scraped and saved to a CSV file for later use by the prediction pipeline. This avoids re-scraping during prediction (which can take 15+ minutes).

```python
OH_UPCOMING_ENABLED = True
UPCOMING_DAY = 'both'   # 'today', 'tomorrow', or 'both'
```

Run:
```bash
python scrape_odds.py
```

**Output files** (saved to `../data/sportsbook_lines_raw/`):
- `betiq_sportsbook_lines.csv` — BetIQ historical lines
- `oh_historical_odds.csv` — OddsHarvester historical lines (appended each run)
- `oh_upcoming_odds.csv` — OddsHarvester upcoming odds (overwritten each run)

### Building team ID mappings (`scrape_new_teams.py`)

To scan ESPN for new teams and update the team ID map:

```bash
python scrape_new_teams.py
```

This scans a configurable range of team IDs on ESPN using CBBpy and adds any new non-D1 teams to `../data/maps/mens_team_map_non_d1.csv`. The D1 team map is provided inside the CBBpy package and is copied to `../data/maps/`.


## Data flow

```
ESPN (CBBpy)           → data/cbb_data_raw/
BetIQ (Selenium)       → data/sportsbook_lines_raw/betiq_sportsbook_lines.csv
OddsHarvester (async)  → data/sportsbook_lines_raw/oh_historical_odds.csv
OddsHarvester upcoming → data/sportsbook_lines_raw/oh_upcoming_odds.csv
```

The `cbb-predictor-model` pipeline reads all of these as inputs.


## Notes

- BetIQ scraping uses Selenium. ChromeDriver must be installed and match your installed Chrome version. The scraper runs headless by default.
- OddsHarvester scrapes [OddsPortal](https://www.oddsportal.com) asynchronously. Upcoming odds can take 15+ minutes for a full day's slate.
- ESPN data goes back to 2003. Earlier seasons have limited data quality.
- Error game IDs are tracked in `data/cbb_data_raw/error_game_ids.csv` so they can be skipped on re-runs.
- Use `USE_EXISTING_GAME_IDS = True` when re-running to avoid re-fetching the full game ID list for already-scraped seasons.
