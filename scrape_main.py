"""
CBBpy Data Scraper for Machine Learning
Scrapes D1 men's basketball game data and boxscores from ESPN using the CBBpy library.
"""

import sys
from pathlib import Path
_this_dir = str(Path(__file__).parent)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from config import *

import os
import cbbpy.mens_scraper as s

# to change ATTEMPS
from cbbpy.utils import cbbpy_utils

import pandas as pd
import time
from datetime import datetime
from typing import List, Set
import tempfile
import shutil
import signal



# ========= CONFIGURATION MACROS =========

# Data collection mode: 'GAME_INFO', 'GAME_STATS', 'BOXSCORES', or 'PBP'
SCRAPE_MODE = 'BOXSCORES'

# Season configuration (ESPN data only availabe from 2003)
START_YEAR = 2026
END_YEAR = 2026

# API call delay (seconds) - adjust to avoid rate limiting
API_DELAY = 0.4

# Request attempts - number of retries for failed requests
cbbpy_utils.ATTEMPTS = 2

# Use existing game_id set stored from previous scrapes if available
USE_EXISTING_GAME_IDS = True

# Skip error game IDs already logged in error_game_ids.csv
SKIP_EXISTING_ERROR_GAME_IDS = False


# ========= EARLY STOPPAGE HANDLING =========
_shutdown_requested = False

def _handle_shutdown(signum, frame):
    """Handle Ctrl+C gracefully"""
    global _shutdown_requested
    print("\n\nShutdown requested. Flushing data, consolidating error log and exiting...")
    _shutdown_requested = True
    # Consolidate error log immediately before exit
    consolidate_error_log()
    exit(0)

signal.signal(signal.SIGINT, _handle_shutdown)

# ========= INPUT/OUTPUT PATHS =========

INPUT_FOLDER = str(SCRAPING_DATA_PATH)
OUTPUT_FOLDER = str(SCRAPING_DATA_PATH)

# TEST_INPUT_FOLDER = PROJECT_ROOT / 'scraping' / 'test_data_raw'
# TEST_OUTPUT_FOLDER = PROJECT_ROOT / 'scraping' / 'test_data_raw'
# INPUT_FOLDER = str(TEST_INPUT_FOLDER)
# OUTPUT_FOLDER = str(TEST_OUTPUT_FOLDER)

# Output file paths combining folder macros with config.py filenames
GAME_INFO_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, GAME_INFO_FILE)
GAME_STATS_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, GAME_STATS_FILE)
BOXSCORE_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, BOXSCORE_FILE)
PBP_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, PBP_FILE)

GAME_INFO_COLUMNS = [
    'game_id', 'game_status', 'home_team', 'home_id', 'home_rank', 'home_record',
    'home_score', 'away_team', 'away_id', 'away_rank', 'away_record', 'away_score',
    'home_point_spread', 'home_win', 'num_ots', 'is_neutral', 'is_postseason',
    'tournament', 'game_day', 'game_time', 'game_loc', 'arena', 'arena_capacity',
    'attendance', 'tv_network', 'referee_1', 'referee_2', 'referee_3',
]

GAME_STATS_COLUMNS = [
    'game_id', 'home_team', 'home_id',
    'home_fga', 'home_fgm', 'home_3pa', 'home_3pm', 'home_fta', 'home_ftm',
    'home_reb', 'home_oreb', 'home_dreb', 'home_ast', 'home_st', 'home_blk',
    'home_to', 'home_techfouls', 'home_flagfouls', 'home_ptsoffto', 'home_fastbreakpts',
    'home_ptsinpaint', 'home_totfouls', 'home_largstlead',
    'away_team', 'away_id',
    'away_fga', 'away_fgm', 'away_3pa', 'away_3pm', 'away_fta', 'away_ftm',
    'away_reb', 'away_oreb', 'away_dreb', 'away_ast', 'away_st', 'away_blk',
    'away_to', 'away_techfouls', 'away_flagfouls', 'away_ptsoffto', 'away_fastbreakpts',
    'away_ptsinpaint', 'away_totfouls', 'away_largstlead', 'year'
]

BOXSCORE_COLUMNS = [
    'game_id', 'team', 'player', 'player_id', 'position', 'starter',
    'min', 'fgm', 'fga', '2pm', '2pa', '3pm', '3pa', 'ftm', 'fta',
    'oreb', 'dreb', 'reb', 'ast', 'stl', 'blk', 'to', 'pf', 'pts'
]

PBP_COLUMNS = [
    'game_id','home_team','away_team','play_desc','home_score','away_score','half',
    'secs_left_half','secs_left_reg','play_team','play_type','shooting_play','scoring_play',
    'is_three','shooter','is_assisted','assist_player','shot_x','shot_y'
]

# Utility Functions
def ensure_output_folder():
    """Create output folder if it doesn't exist."""

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"  Created output folder: {OUTPUT_FOLDER}/")

def ensure_parent_directories(filepath: str):
    """Ensure parent directories exist for a filepath."""

    parent_dir = os.path.dirname(filepath)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

def append_to_csv(df: pd.DataFrame, filepath: str):
    """Append DataFrame to CSV file, creating it if necessary."""

    if df.empty:
        return
    ensure_parent_directories(filepath)
    file_exists = os.path.isfile(filepath)
    
    if file_exists:
        df.to_csv(filepath, mode='a', header=False, index=False)
    else:
        df.to_csv(filepath, mode='w', header=True, index=False)

def get_existing_game_ids(filepath: str) -> Set[str]:
    """
    Get set of game IDs already in the CSV file to avoid duplicates.
    """

    if not os.path.isfile(filepath):
        return set()
    try:
        df = pd.read_csv(filepath, usecols=['game_id'], dtype={'game_id': str})
        return set(df['game_id'].unique())
    except:
        pass
    return set()

def ensure_column_order(df: pd.DataFrame, expected_columns: list) -> pd.DataFrame:
    """
    Ensure DataFrame columns are in the correct order.
    Reorders columns if necessary.
    """

    if df.empty:
        return df
    
    # Find columns that exist in both
    available_columns = [col for col in expected_columns if col in df.columns]

    return df[available_columns]

#API Wrappers (might not even need these since cbbpy funcs should always ret safely)
def get_game_info_safe(game_id: str) -> tuple:
    """Get game info, return (df, error_flag)."""

    try:
        game_info = s.get_game_info(game_id)
        if game_info is None or game_info.empty:
            return pd.DataFrame([]), True
        return game_info, False
    except Exception as e:
        return pd.DataFrame([]), True

def get_game_stats_safe(game_id: str) -> tuple:
    """Get game stats, return (df, error_flag)."""

    try:
        game_stats = s.get_game_stats(game_id)
        if game_stats is None or game_stats.empty:
            return pd.DataFrame([]), True
        return game_stats, False
    except Exception as e:
        return pd.DataFrame([]), True
    
def get_game_boxscores_safe(game_id: str) -> tuple:
    """Get game boxscores, return (df, error_flag)."""

    try:
        game_boxscores = s.get_game_boxscore(game_id)
        if game_boxscores is None or game_boxscores.empty:
            return pd.DataFrame([]), True
        return game_boxscores, False
    except Exception as e:
        return pd.DataFrame([]), True
    
def get_game_pbp_safe(game_id: str) -> tuple:
    """Get game play-by-play, return (df, error_flag)"""

    try:
        game_pbp = s.get_game_pbp(game_id)
        if game_pbp is None or game_pbp.empty:
            return pd.DataFrame([]), True
        return game_pbp, False
    except Exception as e:
        return pd.DataFrame([]), True

def restore_error_game_ids_from_backup():
    """
    restore error_game_ids.csv from append-only error log if CSV is corrupted from early stoppage
    returns true if restoration was performed, False otherwise
    """
    error_ids_path = str(ERROR_IDS_PATH)
    error_log_path = str(ERROR_IDS_PATH).replace('.csv', '.log')
    
    # if CSV is missing/corrupted but log exists, rebuild from log
    file_is_invalid = False
    if not os.path.isfile(error_ids_path):
        file_is_invalid = True
    else:
        try:
            df = pd.read_csv(error_ids_path)
            if len(df) == 0 and os.path.isfile(error_log_path):
                file_is_invalid = True
        except:
            file_is_invalid = True
    
    if file_is_invalid and os.path.isfile(error_log_path):
        try:
            consolidate_error_log()
            print(f"  Rebuilt error_game_ids.csv from error log")
            return True
        except Exception as e:
            print(f"  Warning: Could not rebuild from error log: {e}")
    
    return False

def consolidate_error_log():
    """
    Consolidate the append-only error log into error_game_ids.csv
    This merges log entries with existing CSV to create deduplicated final state
    Called at year completion or graceful shutdown
    """
    error_log_path = str(ERROR_IDS_PATH).replace('.csv', '.log')
    
    if not os.path.isfile(error_log_path):
        return  # No log to consolidate
    
    try:
        # Read existing CSV if it exists
        if os.path.isfile(ERROR_IDS_PATH):
            existing_df = pd.read_csv(ERROR_IDS_PATH)
        else:
            existing_df = pd.DataFrame(columns=['game_id', 'year', 'is_boxscore_error', 'is_game_info_error', 'is_game_stats_error', 'is_pbp_error'])
        
        # Read the log file (simple format: game_id,year,error_type,is_error)
        log_entries = []
        try:
            with open(error_log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(',')
                    if len(parts) >= 4:
                        log_entries.append({
                            'game_id': parts[0],
                            'year': int(parts[1]),
                            'error_type': parts[2],
                            'is_error': parts[3].lower() == 'true'
                        })
        except Exception as e:
            print(f"  Warning: Could not read error log: {e}")
            return
        
        if not log_entries:
            return  # No entries to consolidate
        
        # Build consolidated dataframe by applying log updates
        result_df = existing_df.copy()
        
        for entry in log_entries:
            game_id_str = str(entry['game_id'])
            year = entry['year']
            error_type = entry['error_type']
            is_error = entry['is_error']
            
            # Find or create row
            mask = result_df['game_id'].astype(str) == game_id_str
            
            if mask.any():
                idx = result_df[mask].index[0]
                result_df.loc[idx, f'is_{error_type}_error'] = is_error
            else:
                # Only add if error is True
                if is_error:
                    new_row = pd.DataFrame({
                        'game_id': [game_id_str],
                        'year': [year],
                        'is_boxscore_error': [error_type == 'boxscore'],
                        'is_game_info_error': [error_type == 'game_info'],
                        'is_game_stats_error': [error_type == 'game_stats'],
                        'is_pbp_error': [error_type == 'pbp']
                    })
                    result_df = pd.concat([result_df, new_row], ignore_index=True)
        
        # Remove rows where all error flags are False
        result_df = result_df[
            result_df['is_boxscore_error'] | result_df['is_game_info_error'] | 
            result_df['is_game_stats_error'] | result_df['is_pbp_error']
        ]
        
        # Write consolidated CSV atomically
        temp_fd, temp_path = tempfile.mkstemp(suffix='.csv', dir=os.path.dirname(ERROR_IDS_PATH))
        try:
            os.close(temp_fd)
            result_df.to_csv(temp_path, index=False)
            shutil.move(temp_path, ERROR_IDS_PATH)
            # Clear the log after successful consolidation
            os.remove(error_log_path)
        except Exception as e:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
            raise e
    except Exception as e:
        print(f"  Warning: Could not consolidate error log: {e}")

def log_error_id(game_id: str, year: int, error_type: str, is_error: bool):
    """
    logs errors to temporary error log file.
    error_type can be: 'boxscore', 'game_info', 'game_stats', or 'pbp'
    
    much faster than updating the CSV directly on each error
    """
    error_log_path = str(ERROR_IDS_PATH).replace('.csv', '.log')
    
    try:
        with open(error_log_path, 'a') as f:
            f.write(f"{game_id},{year},{error_type},{is_error}\n")
    except Exception as e:
        print(f"  Warning: Could not write to error log: {e}")


# ========= MAIN SCRAPING FUNCTIONS =========

def get_final_game_ids_from_game_info() -> Set[str]:
    """
    Return game IDs from game_info.csv where game_status is 'Final'.
    Used by scrape_completed_games to restrict GAME_STATS, BOXSCORES, and PBP
    scraping to only completed games, avoiding pointless attempts on scheduled
    or postponed games that would just error out.
    Returns an empty set if game_info.csv does not exist.
    """
    if not os.path.isfile(GAME_INFO_OUTPUT_PATH):
        return set()
    try:
        df = pd.read_csv(
            GAME_INFO_OUTPUT_PATH,
            usecols=['game_id', 'game_status'],
            dtype={'game_id': str, 'game_status': str},
        )
        final_mask = df['game_status'].str.lower() == 'final'
        return set(df.loc[final_mask, 'game_id'].unique())
    except Exception as e:
        print(f"  Warning: Could not read Final game IDs from game_info.csv: {e}")
        return set()


def get_stale_scheduled_game_ids() -> Set[str]:
    """
    Return game IDs in game_info.csv whose game_day has passed but whose
    game_status is not 'Final'. These are games that were scraped while
    scheduled (e.g. from a previous scrape_upcoming_game_info call or an
    early GAME_INFO run) and now need to be re-scraped to get the final result.
    """
    if not os.path.isfile(GAME_INFO_OUTPUT_PATH):
        return set()
    try:
        df = pd.read_csv(
            GAME_INFO_OUTPUT_PATH,
            usecols=['game_id', 'game_status', 'game_day'],
            dtype={'game_id': str, 'game_status': str},
        )
        today = datetime.now().date()
        stale_mask = (
            df['game_status'].str.lower() != 'final'
        ) & (
            pd.to_datetime(df['game_day'], errors='coerce').dt.date < today
        )
        return set(df.loc[stale_mask, 'game_id'].unique())
    except Exception as e:
        print(f"  Warning: Could not identify stale scheduled games: {e}")
        return set()


def remove_game_ids_from_csv(csv_path: str, game_ids: Set[str]) -> int:
    """
    Remove all rows matching the given game_ids from a CSV file.
    Writes atomically via a temp file to avoid corruption.
    Returns the number of rows removed.
    """
    if not game_ids or not os.path.isfile(csv_path):
        return 0
    try:
        df = pd.read_csv(csv_path, dtype={'game_id': str})
        before = len(df)
        df = df[~df['game_id'].isin(game_ids)]
        removed = before - len(df)
        if removed > 0:
            temp_fd, temp_path = tempfile.mkstemp(suffix='.csv', dir=os.path.dirname(csv_path))
            try:
                os.close(temp_fd)
                df.to_csv(temp_path, index=False)
                shutil.move(temp_path, csv_path)
            except Exception as e:
                if os.path.isfile(temp_path):
                    os.remove(temp_path)
                raise e
        return removed
    except Exception as e:
        print(f"  Warning: Could not remove rows from {csv_path}: {e}")
        return 0


def get_all_game_ids_for_season(year: int, use_existing_ids: bool = None, skip_error_ids: bool = None, mode: str = None) -> List[str]:
    """Get all game IDs for a given season.

    Parameters:
        year: Season year (ESPN format)
        use_existing_ids: Override USE_EXISTING_GAME_IDS global (None = use global)
        skip_error_ids: Override SKIP_EXISTING_ERROR_GAME_IDS global (None = use global)
        mode: Override SCRAPE_MODE global for error-type filtering (None = use global)
    """
    _use_existing = USE_EXISTING_GAME_IDS if use_existing_ids is None else use_existing_ids
    _skip_errors  = SKIP_EXISTING_ERROR_GAME_IDS if skip_error_ids is None else skip_error_ids
    _mode         = SCRAPE_MODE if mode is None else mode

    print(f"    Fetching all game IDs for {year} season...")

    if _shutdown_requested:
        return []

    game_id_list = []

    if _use_existing:
        all_ids_path = str(ALL_VALID_GAME_IDS_PATH)
        if os.path.isfile(all_ids_path):
            try:
                #only read game_id and year columns with specified dtypes for faster read
                existing_ids_df = pd.read_csv(all_ids_path, usecols=['game_id', 'year'], dtype={'game_id': str, 'year': int})
                year_data = existing_ids_df[existing_ids_df['year'] == year]
                game_id_list = year_data['game_id'].unique().tolist()
            except:
                game_id_list = []

    if not game_id_list:
        if _shutdown_requested:
            return []

        # fetch game ids using API
        all_game_ids = s.get_game_ids_season(year)

        # save ids to file
        if os.path.isfile(str(ALL_VALID_GAME_IDS_PATH)):
            existing_all_ids_df = pd.read_csv(str(ALL_VALID_GAME_IDS_PATH), usecols=['game_id', 'year'], dtype={'game_id': str, 'year': int})
            # Check for existing (game_id, year) combinations, not just game_id
            year_existing_pairs = set(zip(
                existing_all_ids_df['game_id'],
                existing_all_ids_df['year']
            ))

            #save all IDs from API
            all_ids_to_save = [gid for gid in all_game_ids if (str(gid), year) not in year_existing_pairs]
            if all_ids_to_save:
                append_to_csv(
                    pd.DataFrame({'game_id': all_ids_to_save, 'year': year}),
                    str(ALL_VALID_GAME_IDS_PATH)
                )
        else:
            #file doesn't exist, save all game ids
            append_to_csv(
                pd.DataFrame({'game_id': list(all_game_ids), 'year': year}),
                str(ALL_VALID_GAME_IDS_PATH)
            )
        game_id_list = list(all_game_ids)

    if _skip_errors:
        error_ids_path = str(ERROR_IDS_PATH)
        if os.path.isfile(error_ids_path):
            try:
                error_ids_df = pd.read_csv(error_ids_path, dtype={
                    'game_id': str,
                    'is_boxscore_error': bool,
                    'is_game_info_error': bool,
                    'is_game_stats_error': bool,
                    'is_pbp_error': bool
                })
                error_ids_dict = error_ids_df.set_index('game_id')[['is_boxscore_error', 'is_game_info_error', 'is_game_stats_error', 'is_pbp_error']].to_dict('index')
            except:
                error_ids_dict = {}
        else:
            error_ids_dict = {}

        if _mode == 'GAME_INFO':
            filtered_game_id_list = [
                gid for gid in game_id_list
                if gid not in error_ids_dict or not error_ids_dict[gid].get('is_game_info_error', False)
            ]
        elif _mode == 'GAME_STATS':
            filtered_game_id_list = [
                gid for gid in game_id_list
                if gid not in error_ids_dict or not error_ids_dict[gid].get('is_game_stats_error', False)
            ]
        elif _mode == 'BOXSCORES':
            filtered_game_id_list = [
                gid for gid in game_id_list
                if gid not in error_ids_dict or not error_ids_dict[gid].get('is_boxscore_error', False)
            ]
        elif _mode == 'PBP':
            filtered_game_id_list = [
                gid for gid in game_id_list
                if gid not in error_ids_dict or not error_ids_dict[gid].get('is_pbp_error', False)
            ]
        else:
            filtered_game_id_list = []

        if len(filtered_game_id_list) < len(game_id_list):
            print(f"    Skipping {len(game_id_list) - len(filtered_game_id_list)} error game IDs")
        game_id_list = filtered_game_id_list

    return game_id_list

def scrape_season_data(year: int, existing_ids: Set[str], mode: str = None, use_existing_ids: bool = None, skip_error_ids: bool = None, game_ids: List[str] = None) -> int:
    """
    Scrape data for all games in a season.

    Parameters:
        year: Season year (ESPN format)
        existing_ids: Set of already-scraped game IDs for this mode (modified in place on success)
        mode: Scrape mode override — 'GAME_INFO', 'GAME_STATS', 'BOXSCORES', 'PBP'
              (None = use SCRAPE_MODE global)
        use_existing_ids: Override for USE_EXISTING_GAME_IDS (None = use global).
                          Ignored when game_ids is provided.
        skip_error_ids: Override for SKIP_EXISTING_ERROR_GAME_IDS (None = use global).
                        Ignored when game_ids is provided.
        game_ids: Pre-fetched list of game IDs to scrape. When provided, the internal
                  get_all_game_ids_for_season() call is skipped entirely.

    Returns # of games scraped.
    """
    _mode = SCRAPE_MODE if mode is None else mode

    # determine output path based on mode
    if _mode == 'GAME_INFO':
        output_path = GAME_INFO_OUTPUT_PATH
    elif _mode == 'GAME_STATS':
        output_path = GAME_STATS_OUTPUT_PATH
    elif _mode == 'BOXSCORES':
        output_path = BOXSCORE_OUTPUT_PATH
    elif _mode == 'PBP':
        output_path = PBP_OUTPUT_PATH
    else:
        print(f"Invalid scrape mode: {_mode}")
        return 0

    print(f"\n{'='*70}")
    print(f"Scraping {_mode} for {year} season ({year-1}-{str(year)[-2:]})")
    print(f"{'='*70}")

    if game_ids is not None:
        # Use the caller-supplied list directly (IDs already fetched and cached)
        season_game_ids = game_ids
    else:
        season_game_ids = get_all_game_ids_for_season(year, use_existing_ids=use_existing_ids, skip_error_ids=skip_error_ids, mode=_mode)

    if _shutdown_requested:
        return 0

    # filter out already scraped games
    new_game_ids = [gid for gid in season_game_ids if gid not in existing_ids]

    if len(new_game_ids) < len(season_game_ids):
        print(f"    Skipping {len(season_game_ids) - len(new_game_ids)} already scraped games")

    if not new_game_ids:
        print(f"All games already scraped for {year}")
        return 0

    print(f"    Scraping {len(new_game_ids)} new games...")

    games_scraped = 0
    error_ids_count = 0

    for idx, game_id in enumerate(new_game_ids, 1):

        #check if shutdown was initiated first
        if _shutdown_requested:
            return 0

        data = None
        has_error = False

        # fetch data for game_id:
        # uses wrapper in case of API error or empty data returned,
        # confirms data has correct col format before appending to csv,
        # else logs id to error file
        if _mode == 'GAME_INFO':
            data, has_error = get_game_info_safe(game_id)
            time.sleep(API_DELAY)
            if not data.empty and not has_error:
                data['year'] = year
                data = ensure_column_order(data, GAME_INFO_COLUMNS)
                append_to_csv(data, output_path)
            else:
                log_error_id(game_id, year, 'game_info', True)
                error_ids_count += 1

        elif _mode == 'GAME_STATS':
            data, has_error = get_game_stats_safe(game_id)
            time.sleep(API_DELAY)
            if not data.empty and not has_error:
                data['year'] = year
                data = ensure_column_order(data, GAME_STATS_COLUMNS)
                append_to_csv(data, output_path)
            else:
                log_error_id(game_id, year, 'game_stats', True)
                error_ids_count += 1

        elif _mode == 'BOXSCORES':
            data, has_error = get_game_boxscores_safe(game_id)
            time.sleep(API_DELAY)
            if not data.empty and not has_error:
                data['game_id'] = game_id
                data = ensure_column_order(data, BOXSCORE_COLUMNS)
                append_to_csv(data, output_path)
            else:
                log_error_id(game_id, year, 'boxscore', True)
                error_ids_count += 1

        elif _mode == 'PBP':
            data, has_error = get_game_pbp_safe(game_id)
            time.sleep(API_DELAY)
            if not data.empty and not has_error:
                data['game_id'] = game_id
                data = ensure_column_order(data, PBP_COLUMNS)
                append_to_csv(data, output_path)
            else:
                log_error_id(game_id, year, 'pbp', True)
                error_ids_count += 1

        #mark game as successfully scraped
        if not has_error and data is not None and not data.empty:
            existing_ids.add(game_id)
            games_scraped += 1

        if idx % 10 == 0:
            print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")

    if games_scraped > 0:
        print(f"    Successfully scraped and saved {games_scraped} games")
    else:
        print(f"    No game data collected for {year}")

    if error_ids_count > 0:
        print(f"    Logged {error_ids_count} error game IDs")

    # consolidate error log into CSV
    consolidate_error_log()

    return games_scraped


def scrape_completed_games(years: list, modes: list) -> dict:
    """
    Scrape new completed games for the given season years and scrape modes.
    Designed to be called from an external orchestrator (e.g. update_data.py).

    Key behaviors:
    - Fetches game IDs from ESPN once per season year (not once per mode) so
      that all_valid_game_ids.csv is updated a single time and then reused
      across all modes, avoiding redundant API calls.
    - Always re-fetches game IDs from ESPN (ignores cached ID list) to catch
      newly scheduled or rescheduled games.
    - Never skips error-logged game IDs so that games that previously returned
      null (e.g. not-yet-played games) are retried once they have completed.
    - Deduplication against the existing output CSV prevents re-scraping games
      that are already collected.
    - For GAME_INFO: detects and re-scrapes rows where game_status is not
      'Final' but the game_day has now passed (games scraped while scheduled
      that have since been played).

    Parameters:
        years:  List of season years in ESPN format (e.g. [2026])
        modes:  List of scrape modes, e.g. ['GAME_INFO', 'GAME_STATS', 'BOXSCORES', 'PBP']

    Returns:
        dict mapping each mode to {'scraped': int} with total games newly scraped.
    """
    mode_output_paths = {
        'GAME_INFO':  GAME_INFO_OUTPUT_PATH,
        'GAME_STATS': GAME_STATS_OUTPUT_PATH,
        'BOXSCORES':  BOXSCORE_OUTPUT_PATH,
        'PBP':        PBP_OUTPUT_PATH,
    }

    valid_modes = [m for m in modes if m in mode_output_paths]
    if len(valid_modes) < len(modes):
        for m in modes:
            if m not in mode_output_paths:
                print(f"  Skipping unknown scrape mode: {m}")

    ensure_output_folder()
    restore_error_game_ids_from_backup()

    # --- Fetch game IDs once per season year, shared across all modes ---
    print("\n" + "=" * 70)
    print("Fetching season game IDs from ESPN...")
    print("=" * 70)
    season_game_ids = {}
    for year in years:
        if _shutdown_requested:
            return {}
        ids = get_all_game_ids_for_season(year, use_existing_ids=False, skip_error_ids=False)
        season_game_ids[year] = ids
        print(f"  Year {year}: {len(ids)} game IDs")

    # For non-GAME_INFO modes, restrict to game IDs confirmed Final in game_info.csv.
    # This avoids scraping stats/boxscores/PBP for scheduled or postponed games.
    final_game_ids = get_final_game_ids_from_game_info()
    if final_game_ids:
        print(f"  {len(final_game_ids)} Final game IDs found in game_info.csv "
              f"(used to filter GAME_STATS / BOXSCORES / PBP)")
    else:
        print("  Warning: no Final game IDs found in game_info.csv — "
              "GAME_STATS / BOXSCORES / PBP will be skipped unless GAME_INFO runs first")

    results = {}

    for mode in valid_modes:
        if _shutdown_requested:
            break

        output_path = mode_output_paths[mode]

        # Load existing IDs for this mode's output file
        existing_ids = get_existing_game_ids(output_path)
        if existing_ids:
            print(f"\n[{mode}] {len(existing_ids)} already-scraped game IDs in output file")

        # --- GAME_INFO: detect stale scheduled rows and re-scrape them ---
        if mode == 'GAME_INFO':
            stale_ids = get_stale_scheduled_game_ids()
            stale_to_retry = stale_ids & existing_ids
            if stale_to_retry:
                removed = remove_game_ids_from_csv(output_path, stale_to_retry)
                existing_ids -= stale_to_retry
                print(
                    f"[GAME_INFO] {len(stale_to_retry)} stale scheduled game(s) found "
                    f"(game_day passed, not Final) — removed {removed} row(s) to re-scrape"
                )

        total_scraped = 0

        for year in years:
            if _shutdown_requested:
                break

            if mode == 'GAME_INFO':
                # Use the full season ID list — GAME_INFO can scrape scheduled games too
                mode_game_ids = season_game_ids[year]
            else:
                # Restrict to IDs that are confirmed Final in game_info.csv
                mode_game_ids = [gid for gid in season_game_ids[year] if gid in final_game_ids]
                filtered_out = len(season_game_ids[year]) - len(mode_game_ids)
                if filtered_out:
                    print(f"    [{mode}] Skipping {filtered_out} non-Final game ID(s) "
                          f"for {year} season (not yet completed per game_info.csv)")

            scraped = scrape_season_data(
                year,
                existing_ids,
                mode=mode,
                skip_error_ids=False,       # retry previously-errored games
                game_ids=mode_game_ids,
            )
            total_scraped += scraped

        results[mode] = {'scraped': total_scraped}

    return results


# ========= Main scraping function =========
def run_scraper():
    """Main function to run the scraper based on configuration"""

    print("="*70)
    print("CBBpy Data Scraper for Machine Learning")
    print("="*70)
    print(f"Mode: {SCRAPE_MODE}")
    print(f"Seasons: {START_YEAR} to {END_YEAR}")
    print(f"API Delay: {API_DELAY}s")
    print(f"Output Folder: {OUTPUT_FOLDER}/")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    ensure_output_folder()

    if restore_error_game_ids_from_backup():
        print("  Corrupted error_game_ids.csv was restored from backup\n")


    output_file = ''

    if SCRAPE_MODE == 'GAME_INFO':
        output_file = GAME_INFO_OUTPUT_PATH
    elif SCRAPE_MODE == 'GAME_STATS':
        output_file = GAME_STATS_OUTPUT_PATH
    elif SCRAPE_MODE == 'BOXSCORES':
        output_file = BOXSCORE_OUTPUT_PATH
    elif SCRAPE_MODE == 'PBP':
        output_file = PBP_OUTPUT_PATH
    else:
        print(f"Invalid SCRAPE_MODE: {SCRAPE_MODE}")
        return
    
    print(f"\nOutput file for {SCRAPE_MODE} mode: {output_file}")
    existing_ids = get_existing_game_ids(output_file)
    
    if existing_ids:
        print(f"  Found {len(existing_ids)} existing game IDs in output file")
    
    total_seasons = END_YEAR - START_YEAR + 1
    total_games_scraped = 0
    
    for season_idx, year in enumerate(range(START_YEAR, END_YEAR + 1), 1):
        #check if shutdown was initiated first
        if _shutdown_requested:
            return
        
        print(f"\n[Season {season_idx}/{total_seasons}]")
        
        try:
            # scrape season data and write to file
            games_scraped = scrape_season_data(year, existing_ids)
            total_games_scraped += games_scraped
        except Exception as e:
            print(f"    Error processing season {year}: {e}")
            if _shutdown_requested:
                return
            continue
        
        if year < END_YEAR:
            time.sleep(API_DELAY)
    
    print(f"\n{'='*70}")
    print("SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"Mode: {SCRAPE_MODE}")
    print(f"Output file: {output_file}")
    print(f"Total games scraped: {total_games_scraped}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\nOutput file:")
    print(f"  - {output_file}")
    if os.path.isfile(output_file):
        try:
            game_info_df = pd.read_csv(output_file)
            print(f"\nGame Info statistics:")
            print(f"  Total rows: {len(game_info_df):,}")
            if 'game_id' in game_info_df.columns:
                print(f"  Unique games: {game_info_df['game_id'].nunique():,}")
        except Exception as e:
            print(f"  Could not read game_info statistics: {e}")
    
    print(f"\n{'='*70}\n")

def scrape_upcoming_game_info(days_ahead: int = 0) -> pd.DataFrame:
    """
    Scrape game_info for upcoming games within the next X days.

    Uses CBBpy's get_games_range() to fetch game info for future dates.
    Only returns scheduled/upcoming games (not already-completed games).

    Parameters:
        days_ahead: Number of days ahead to scrape (0 = today only,
                    1 = today + tomorrow, etc.)

    Returns:
        DataFrame with GAME_INFO_COLUMNS (scores will be NaN for unplayed games).
        Also saves to data/cbb_data_raw/upcoming_game_info.csv.
    """
    from datetime import timedelta

    today = datetime.now()
    end_date = today + timedelta(days=days_ahead)

    start_str = today.strftime('%m/%d/%Y')
    end_str = end_date.strftime('%m/%d/%Y')

    print(f"Scraping upcoming game info from {start_str} to {end_str}...")

    try:
        # CBBpy get_games_range returns (game_info_df, boxscore_df, pbp_df)
        # We only want game_info, so set box=False, pbp=False
        game_info_df, _, _ = s.get_games_range(
            start_date=start_str,
            end_date=end_str,
            info=True,
            box=False,
            pbp=False,
        )
    except Exception as e:
        print(f"  Error fetching upcoming games: {e}")
        return pd.DataFrame(columns=GAME_INFO_COLUMNS)

    if game_info_df is None or game_info_df.empty:
        print("  No upcoming games found")
        return pd.DataFrame(columns=GAME_INFO_COLUMNS)

    # Filter to only scheduled/upcoming games (not Final)
    if 'game_status' in game_info_df.columns:
        scheduled_mask = game_info_df['game_status'].str.lower() != 'final'
        game_info_df = game_info_df[scheduled_mask].copy()

    if game_info_df.empty:
        print("  All games in date range are already completed")
        return pd.DataFrame(columns=GAME_INFO_COLUMNS)

    # Determine season year (CBB season year is the later year, e.g. 2025-26 season = 2026)
    current_month = today.month
    if current_month >= 11:
        season_year = today.year + 1
    else:
        season_year = today.year

    game_info_df['year'] = season_year

    # Ensure column order
    game_info_df = ensure_column_order(game_info_df, GAME_INFO_COLUMNS + ['year'])

    print(f"  Found {len(game_info_df)} upcoming games")

    # Save to file (use literal filename to avoid config module shadowing)
    upcoming_output_path = os.path.join(OUTPUT_FOLDER, 'upcoming_game_info.csv')
    game_info_df.to_csv(upcoming_output_path, index=False)
    print(f"  Saved to {upcoming_output_path}")

    return game_info_df


if __name__ == "__main__":
    run_scraper()