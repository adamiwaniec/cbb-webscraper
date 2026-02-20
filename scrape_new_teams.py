"""
Simple script to scrape new non-D1 college basketball teams.
Also copies D1 team map from CBBpy into new maps directory for use in CBB Predictor Model.

Note:
    Many teams on ESPN are non-existent or are in other leagues.
    But for my personal purposes this isn't a problem, as long as non-D1 team IDs are pulled.
"""


import sys
import importlib.resources
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import *

import cbbpy
from cbbpy.utils import cbbpy_utils
from cbbpy.utils.cbbpy_utils import build_team_map

# request attempts - number of retries for failed requests
cbbpy_utils.ATTEMPTS = 1


if __name__ == '__main__':
    # copy CBBpy D1 team map into data/maps/ using imported CBBpy package
    if not TEAM_MAP_PATH.exists():
        mens_team_map_cbbpy_path = importlib.resources.read_text(cbbpy.utils, 'mens_team_map.csv')
        TEAM_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TEAM_MAP_PATH, 'w', encoding='utf-8') as f:
            f.write(mens_team_map_cbbpy_path)
        print(f"Copied D1 team map from CBBpy to {TEAM_MAP_PATH}")

    try:
        build_team_map(
            start_id=1,
            end_id=10000,
            existing_d1_map_file=TEAM_MAP_PATH,
            output_file=NON_DIVISION_TEAM_MAP_PATH,
            game_type='mens',
            api_delay_range=(0.1, 0.5) # (seconds), adjust as needed to avoid rate limiting
        )
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user. Exiting...")
        sys.exit(0)
