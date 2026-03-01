from pathlib import Path


### DEFINE PATHS + FILENAMES

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT.parent / 'data'

CBB_MAPS_PATH = DATA_PATH / 'maps'
SCRAPING_DATA_PATH = DATA_PATH / 'cbb_data_raw'

PBP_FILE = 'pbp_data.csv'
BOXSCORE_FILE = 'boxscore_data.csv'
GAME_INFO_FILE = 'game_info.csv'
GAME_STATS_FILE = 'game_stats.csv'

PLAYER_MAP_FILE = 'players.csv'
TEAM_MAP_FILE = 'mens_team_map.csv'
NON_DIVISION_TEAM_MAP_FILE = 'mens_team_map_non_d1.csv'

PLAYER_MAP_PATH = CBB_MAPS_PATH / PLAYER_MAP_FILE
TEAM_MAP_PATH = CBB_MAPS_PATH / TEAM_MAP_FILE
NON_DIVISION_TEAM_MAP_PATH = CBB_MAPS_PATH / NON_DIVISION_TEAM_MAP_FILE

ERROR_IDS_PATH = SCRAPING_DATA_PATH / 'error_game_ids.csv'
ALL_VALID_GAME_IDS_PATH = SCRAPING_DATA_PATH / 'all_valid_game_ids.csv'

SPORTSBOOK_LINES_RAW_PATH = DATA_PATH / 'sportsbook_lines_raw'

# BetIQ sportsbook lines (historical, scraped from betiq.teamrankings.com)
BETIQ_SPORTSBOOK_LINES_FILE = 'betiq_sportsbook_lines.csv'
BETIQ_SPORTSBOOK_LINES_PATH = SPORTSBOOK_LINES_RAW_PATH / BETIQ_SPORTSBOOK_LINES_FILE

# OddsHarvester sportsbook lines
OH_HISTORICAL_ODDS_FILE = 'oh_historical_odds.csv'
OH_UPCOMING_ODDS_FILE = 'oh_upcoming_odds.csv'
OH_HISTORICAL_ODDS_PATH = SPORTSBOOK_LINES_RAW_PATH / OH_HISTORICAL_ODDS_FILE
OH_UPCOMING_ODDS_PATH = SPORTSBOOK_LINES_RAW_PATH / OH_UPCOMING_ODDS_FILE

# Upcoming game data
UPCOMING_GAME_INFO_FILE = 'upcoming_game_info.csv'