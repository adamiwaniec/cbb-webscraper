"""Simple script to scrape new non-D1 college basketball teams."""


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import *

from cbbpy.utils import cbbpy_utils
from cbbpy.utils.cbbpy_utils import build_team_map

# request attempts - number of retries for failed requests
cbbpy_utils.ATTEMPTS = 1


if __name__ == '__main__':
    try:
        build_team_map(
            start_id=0,
            end_id=100,
            existing_d1_map_file=TEAM_MAP_PATH,
            output_file=NON_DIVISION_TEAM_MAP_PATH,
            game_type='mens',
            api_delay_range=(0.1, 0.5) # (seconds), adjust as needed to avoid rate limiting
        )
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user. Exiting...")
        sys.exit(0)
