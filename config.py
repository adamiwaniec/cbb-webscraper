from pathlib import Path


### DEFINE PATHS + FILENAMES

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT.parent / 'data'

CBB_MAPS_PATH = DATA_PATH / 'maps'
SCRAPING_DATA_PATH = DATA_PATH / 'cbb_data_raw'

PBP_FILE = 'pbp_data.csv'
BOXSCORE_FILE = 'boxscore_data.csv'
GAME_DATA_FILE = 'game_data.csv'
GAME_INFO_FILE = 'game_info.csv'
GAME_STATS_FILE = 'game_stats.csv'

PLAYER_MAP_FILE = 'players.csv'
TEAM_MAP_FILE = 'mens_team_map.csv'
NON_DIVISION_TEAM_MAP_FILE = 'non_division_team_map.csv'

PLAYER_MAP_PATH = CBB_MAPS_PATH / PLAYER_MAP_FILE
TEAM_MAP_PATH = CBB_MAPS_PATH / TEAM_MAP_FILE
NON_DIVISION_TEAM_MAP_PATH = CBB_MAPS_PATH / NON_DIVISION_TEAM_MAP_FILE

ERROR_IDS_PATH = SCRAPING_DATA_PATH / 'error_game_ids.csv'
ALL_VALID_GAME_IDS_PATH = SCRAPING_DATA_PATH / 'all_valid_game_ids.csv'