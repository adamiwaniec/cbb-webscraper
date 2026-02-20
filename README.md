# CBB WebScraper

A Python web scraper for collecting NCAA Division 1 men's college basketball game data from ESPN, going back to 2003.

## Installation

### Requirements
- Python 3.8+
- My fork of the CBBpy library: https://github.com/adamiwaniec/CBBpy

All other package dependencies should be installed automatically with CBBpy.

### Setup

1. Clone this repository:
```bash
git clone https://github.com/adamiwaniec/cbb-webscraper.git
cd cbb-webscraper
```

2. Install the custom CBBpy fork from GitHub:
```bash
pip install git+https://github.com/adamiwaniec/CBBpy.git
```

Or if you have CBBpy cloned locally:
```bash
pip install /path/to/CBBpy
```

## Usage

Edit these configuration options at the top of `scrape_main.py`:

```python
SCRAPE_MODE = 'GAME_STATS'
START_YEAR = 2021
END_YEAR = 2026
```
Others may be left on the default values.


Run the scraper:
```bash
python scrape_main.py
```

Data is saved to `../data/cbb_data_raw/`

## Mapping team names to numeric IDs

To scrape and build a map of college basketball teams, use the utility script:

```bash
python scrape_new_teams.py
```

This will scan a range of team IDs on ESPN using cbbpy and add any non-D1 teams to the output map file. Configure the ID range and file paths in the cbbpy API function call as needed.

A D1 team map is provided inside the CBBpy package, which this script will copy into the same data/maps/ directory as the other map.

## Output Data Modes

- **GAME_INFO**: Game information (scores, teams, dates, rankings)
- **GAME_STATS**: Team-level statistics (shooting, rebounds, turnovers)
- **BOXSCORES**: Player-level statistics
- **PBP**: Play-by-play data
