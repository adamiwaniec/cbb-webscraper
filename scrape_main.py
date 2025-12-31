"""
CBBpy Data Scraper for Machine Learning
Scrapes D1 men's basketball game data and boxscores from ESPN using the CBBpy library.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import *

import os
import cbbpy.mens_scraper as s

# to change ATTEMPS
from cbbpy.utils import cbbpy_utils

import pandas as pd
import time
from datetime import datetime
from typing import List, Set



# ========= CONFIGURATION MACROS =========

# Data collection mode: 'GAME_INFO', 'GAME_STATS', or 'BOXSCORES'
SCRAPE_MODE = 'GAME_STATS'

# Season configuration
START_YEAR = 2005  # First season to scrape
END_YEAR = 2026    # Last season to scrape

# Season type: 'reg' or 'post' or 'all'
SEASON_TYPE = 'all'

# Post season type: 'march_madness' or 'all'
POSTSEASON_TYPE = 'all'

# Get march madness first four games: 'True' or 'False'
MARCH_MADNESS_FIRST_FOUR = True

# API call delay (seconds) - adjust to avoid rate limiting
API_DELAY = 0.1

# Request attempts - number of retries for failed requests
cbbpy_utils.ATTEMPTS = 5

# Use existing game_ids stored from previous calls to 
# get_all_game_ids_for_season()
USE_EXISTING_GAME_IDS = True

# Skip error game IDs already logged in error_game_ids.csv
SKIP_EXISTING_ERROR_GAME_IDS = False

# ========= INPUT/OUTPUT PATHS =========

INPUT_FOLDER = str(SCRAPING_DATA_PATH)
OUTPUT_FOLDER = str(SCRAPING_DATA_PATH)

TEST_INPUT_FOLDER = PROJECT_ROOT / 'scraping' / 'test_data_raw'
TEST_OUTPUT_FOLDER = PROJECT_ROOT / 'scraping' / 'test_data_raw'
# INPUT_FOLDER = str(TEST_INPUT_FOLDER)
# OUTPUT_FOLDER = str(TEST_OUTPUT_FOLDER)

# Output file paths combining folder macros with config.py filenames
GAME_INFO_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, GAME_INFO_FILE)
GAME_STATS_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, GAME_STATS_FILE)
BOXSCORE_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, BOXSCORE_FILE)

GAME_DATA_COLUMNS = [
    'game_id', 'game_status', 'home_team', 'home_id', 'home_rank', 'home_record',
    'home_score', 'away_team', 'away_id', 'away_rank', 'away_record', 'away_score',
    'home_point_spread', 'home_win', 'num_ots', 'is_neutral', 'is_postseason',
    'tournament', 'game_day', 'game_time', 'game_loc', 'arena', 'arena_capacity',
    'attendance', 'tv_network', 'referee_1', 'referee_2', 'referee_3',
    'home_fga', 'home_fgm', 'home_3pa', 'home_3pm', 'home_fta', 'home_ftm',
    'home_reb', 'home_oreb', 'home_dreb', 'home_ast', 'home_st', 'home_blk',
    'home_to', 'home_techfouls', 'home_flagfouls', 'home_ptsoffto', 'home_fastbreakpts',
    'home_ptsinpaint', 'home_totfouls', 'home_largstlead',
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
        df = pd.read_csv(filepath, low_memory=False)
        if 'game_id' in df.columns:
            return set(df['game_id'].astype(str).unique())
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

def should_include_game(game_info: pd.DataFrame) -> bool:
    """Filter games based on SEASON_TYPE and POSTSEASON_TYPE."""

    if game_info.empty:
        return False
    
    if 'is_postseason' not in game_info.columns or 'tournament' not in game_info.columns:
        return True
    
    is_postseason = game_info['is_postseason'].iloc[0]
    tournament = game_info['tournament'].iloc[0] if pd.notna(game_info['tournament'].iloc[0]) else ""
    
    # Filter based on SEASON_TYPE
    if SEASON_TYPE == 'reg':

        if is_postseason:
            return False
    elif SEASON_TYPE == 'post':
        if not is_postseason:
            return False
        if POSTSEASON_TYPE == 'march_madness':
            if not tournament.startswith("Men's Basketball Championship"):
                return False
            # Filter first four games
            if not MARCH_MADNESS_FIRST_FOUR and "First Four" in tournament:
                return False
    # elif season_type == 'all':
    #     # Include all games, but still filter by POSTSEASON_TYPE if it's postseason
    #     if is_postseason and POSTSEASON_TYPE == 'march_madness':
    #         if not tournament.startswith("Men's Basketball Championship"):
    #             return False
    
    return True

# Safe API Wrappers
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

def update_error_game_ids(game_id: str, year: int, is_boxscore_error: bool = False, is_game_info_error: bool = False, is_game_stats_error: bool = False):
    """
    Update error_game_ids.csv with flags for boxscore, game_info, and game_stats errors.
    Unified schema with three boolean columns for each error type.
    Handles both new entries and updates to existing entries using OR logic.
    
    Ensures no duplicates are created by checking if the game_id already exists.
    If it does, updates the row with OR logic for error flags.
    If not, adds a new row.
    """

    error_ids_path = str(ERROR_IDS_PATH)
    

    if os.path.isfile(error_ids_path):
        try:
            error_ids_df = pd.read_csv(error_ids_path)
            # ensure game_id column is stored as string for consistent comparison
            error_ids_df['game_id'] = error_ids_df['game_id'].astype(str)
        except:
            error_ids_df = pd.DataFrame(columns=['game_id', 'year', 'is_boxscore_error', 'is_game_info_error', 'is_game_stats_error'])
    else:
        error_ids_df = pd.DataFrame(columns=['game_id', 'year', 'is_boxscore_error', 'is_game_info_error', 'is_game_stats_error'])
    
    # Normalize game_id to string for comparison
    game_id_str = str(game_id)
    
    existing_row_mask = error_ids_df['game_id'].astype(str) == game_id_str
    
    if existing_row_mask.any():
        # Update existing row - OR the error flags (True if either is True)
        idx = error_ids_df[existing_row_mask].index[0]
        error_ids_df.loc[idx, 'is_boxscore_error'] = bool(error_ids_df.loc[idx, 'is_boxscore_error']) or is_boxscore_error
        error_ids_df.loc[idx, 'is_game_info_error'] = bool(error_ids_df.loc[idx, 'is_game_info_error']) or is_game_info_error
        error_ids_df.loc[idx, 'is_game_stats_error'] = bool(error_ids_df.loc[idx, 'is_game_stats_error']) or is_game_stats_error
    else:
        new_row = pd.DataFrame({
            'game_id': [game_id_str],
            'year': [year],
            'is_boxscore_error': [is_boxscore_error],
            'is_game_info_error': [is_game_info_error],
            'is_game_stats_error': [is_game_stats_error]
        })
        error_ids_df = pd.concat([error_ids_df, new_row], ignore_index=True)
    
    # write back to CSV
    error_ids_df.to_csv(error_ids_path, index=False)

def mark_game_as_valid(game_id: str):
    """
    Remove a game_id from the error_game_ids.csv file.
    This is called when a previously errored game now has valid data.
    
    Returns:
        bool: True if game was found and removed, False if game_id not in error file
    """
    error_ids_path = str(ERROR_IDS_PATH)
    
    if not os.path.isfile(error_ids_path):
        return False
    
    try:
        error_ids_df = pd.read_csv(error_ids_path)
        error_ids_df['game_id'] = error_ids_df['game_id'].astype(str)
    except:
        return False
    
    # convert game_id to string for comparison
    game_id_str = str(game_id)
    
    existing_rows_mask = error_ids_df['game_id'] == game_id_str
    
    if not existing_rows_mask.any():
        return False
    
    # Remove all rows with this game_id (clean slate now that it has valid data)
    error_ids_df = error_ids_df[~existing_rows_mask]
    
    # Write back to CSV
    error_ids_df.to_csv(error_ids_path, index=False)
    
    return True

def remove_error_game_ids_from_output(output_file: str, scrape_mode: str):
    """
    Remove any rows from the output file that correspond to game_ids in the error_game_ids.csv file
    with a matching error type for the current SCRAPE_MODE.
    
    For GAME_INFO mode: only removes games with is_game_info_error=True
    For GAME_STATS mode: only removes games with is_game_stats_error=True
    For BOXSCORES mode: only removes games with is_boxscore_error=True
    
    This ensures we don't have error games mixed in with valid data.
    Should be called at the end of scraping before finalizing the output.
    """

    error_ids_path = str(ERROR_IDS_PATH)
    
    if not os.path.isfile(output_file) or not os.path.isfile(error_ids_path):
        return 0
    
    try:
        error_ids_df = pd.read_csv(error_ids_path)
        output_df = pd.read_csv(output_file)
        
        # Convert game_id to string for comparison
        error_ids_df['game_id'] = error_ids_df['game_id'].astype(str)
        output_df['game_id'] = output_df['game_id'].astype(str)
        
        # Filter error IDs based on scrape mode error type
        if scrape_mode == 'GAME_INFO':
            error_game_ids = set(error_ids_df[error_ids_df['is_game_info_error'] == True]['game_id'].astype(str))
        elif scrape_mode == 'GAME_STATS':
            error_game_ids = set(error_ids_df[error_ids_df['is_game_stats_error'] == True]['game_id'].astype(str))
        elif scrape_mode == 'BOXSCORES':
            error_game_ids = set(error_ids_df[error_ids_df['is_boxscore_error'] == True]['game_id'].astype(str))
        else:
            return 0
        
        # Find rows with error game_ids
        error_rows_mask = output_df['game_id'].isin(error_game_ids)
        rows_removed = error_rows_mask.sum()
        
        if rows_removed > 0:
            output_df = output_df[~error_rows_mask]
            output_df.to_csv(output_file, index=False)
        else:
            output_df.to_csv(output_file, index=False)
        
        return rows_removed
    except Exception as e:
        print(f"Warning: Could not remove error game_ids from output: {e}")
        return 0


# ========= MAIN SCRAPING FUNCTIONS =========

def get_all_game_ids_for_season(year: int) -> List[str]:
    """Get all game IDs for a given season."""

    print(f"    Fetching all game IDs for {year} season...")

    game_id_list = []

    if USE_EXISTING_GAME_IDS:
        all_ids_path = str(ALL_VALID_GAME_IDS_PATH)
        if os.path.isfile(all_ids_path):
            try:
                existing_ids_df = pd.read_csv(all_ids_path)
                year_data = existing_ids_df[existing_ids_df['year'] == year]
                game_id_list = year_data['game_id'].astype(str).unique().tolist()
            except:
                game_id_list = []

    if not game_id_list:
        # fetch game ids using API
        all_game_ids = s.get_game_ids_season(year, SEASON_TYPE)

        # save ids to file
        if os.path.isfile(str(ALL_VALID_GAME_IDS_PATH)):
            existing_all_ids_df = pd.read_csv(str(ALL_VALID_GAME_IDS_PATH))
            existing_ids_set = set(existing_all_ids_df['game_id'].astype(str).unique())
            new_ids = [gid for gid in all_game_ids if gid not in existing_ids_set]
            if new_ids:
                append_to_csv(
                    pd.DataFrame({'game_id': new_ids, 'year': year}),
                    str(ALL_VALID_GAME_IDS_PATH)
                )
        append_to_csv(
            pd.DataFrame({'game_id': list(all_game_ids), 'year': year}),
            str(ALL_VALID_GAME_IDS_PATH)
        )
        game_id_list = list(all_game_ids)

    if SKIP_EXISTING_ERROR_GAME_IDS:
        error_ids_path = str(ERROR_IDS_PATH)
        if os.path.isfile(error_ids_path):
            try:
                error_ids_df = pd.read_csv(error_ids_path)
                error_ids_dict = {}
                for _, row in error_ids_df.iterrows():
                    error_ids_dict[str(row['game_id'])] = {
                        'is_boxscore_error': bool(row.get('is_boxscore_error', False)),
                        'is_game_info_error': bool(row.get('is_game_info_error', False)),
                        'is_game_stats_error': bool(row.get('is_game_stats_error', False))
                    }
            except:
                error_ids_dict = {}
        else:
            error_ids_dict = {}

        if SCRAPE_MODE == 'GAME_INFO':
            filtered_game_id_list = [
                gid for gid in game_id_list 
                if gid not in error_ids_dict or not error_ids_dict[gid].get('is_game_info_error', False)
            ]
        elif SCRAPE_MODE == 'GAME_STATS':
            filtered_game_id_list = [
                gid for gid in game_id_list 
                if gid not in error_ids_dict or not error_ids_dict[gid].get('is_game_stats_error', False)
            ]
        elif SCRAPE_MODE == 'BOXSCORES':
            filtered_game_id_list = [
                gid for gid in game_id_list 
                if gid not in error_ids_dict or not error_ids_dict[gid].get('is_boxscore_error', False)
            ]
        else:
            filtered_game_id_list = []
            
        if len(filtered_game_id_list) < len(game_id_list):
            print(f"    Skipping {len(game_id_list) - len(filtered_game_id_list)} error game IDs")
        game_id_list = filtered_game_id_list
    
    return game_id_list

def scrape_season_data(year: int, existing_ids: Set[str]) -> int:
    """
    Scrape data for all games in a season based on SCRAPE_MODE.
    
    Returns # of games scraped.
    """
    
    print(f"\n{'='*70}")
    print(f"Scraping {SCRAPE_MODE} for {year} season ({year-1}-{str(year)[-2:]})")
    print(f"{'='*70}")
    
    game_ids = get_all_game_ids_for_season(year)
    
    # filter out already scraped games
    new_game_ids = [gid for gid in game_ids if gid not in existing_ids]
    
    if len(new_game_ids) < len(game_ids):
        print(f"    Skipping {len(game_ids) - len(new_game_ids)} already scraped games")
    
    if not new_game_ids:
        print(f"All games already scraped for {year}")
        return 0
    
    print(f"    Scraping {len(new_game_ids)} new games...")
    
    games_scraped = 0
    error_ids_count = 0
    
    for idx, game_id in enumerate(new_game_ids, 1):
        # game_info = pd.DataFrame()
        # game_stats = pd.DataFrame()
        # info_error = False
        # stats_error = False
        
        # fetch game info
        if SCRAPE_MODE == 'GAME_INFO':
            game_info, info_error = get_game_info_safe(game_id)
            time.sleep(API_DELAY)

            if game_info.empty or info_error:
                update_error_game_ids(game_id, year, is_game_info_error=True)
                error_ids_count += 1
                if idx % 10 == 0:
                    print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
                continue
            
            game_info['year'] = year
            append_to_csv(game_info, GAME_INFO_OUTPUT_PATH)
        
        # fetch game stats
        if SCRAPE_MODE == 'GAME_STATS':
            game_stats, stats_error = get_game_stats_safe(game_id)
            time.sleep(API_DELAY)

            if game_stats.empty or stats_error:
                update_error_game_ids(game_id, year, is_game_stats_error=True)
                error_ids_count += 1
                if idx % 10 == 0:
                    print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
                continue

            game_stats['year'] = year
            append_to_csv(game_stats, GAME_STATS_OUTPUT_PATH)

        # fetch game boxscores
        if SCRAPE_MODE == 'GAME_BOXSCORES':
            game_boxscores, boxscore_error = get_game_boxscores_safe(game_id)
            time.sleep(API_DELAY)

            if game_boxscores.empty or boxscore_error:
                update_error_game_ids(game_id, year, is_boxscore_error=True)
                error_ids_count += 1
                if idx % 10 == 0:
                    print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
                continue

            game_boxscores['year'] = year
            append_to_csv(game_boxscores, BOXSCORE_OUTPUT_PATH)
        
        # if info_error or stats_error:
            # Update error file with error flags
            # update_error_game_ids(game_id, year, is_game_info_error=info_error, is_game_stats_error=stats_error)
            # error_ids_count += 1
            
            # if idx % 10 == 0:
            #     print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
            # continue
        
        # Perform basic validation
        # if scrape_info and game_info.empty:
        #     update_error_game_ids(game_id, year, is_game_info_error=True, is_game_stats_error=stats_error)
        #     error_ids_count += 1
        #     if idx % 10 == 0:
        #         print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
        #     continue
        
        # if scrape_stats and game_stats.empty:
        #     update_error_game_ids(game_id, year, is_game_info_error=info_error, is_game_stats_error=True)
        #     error_ids_count += 1
        #     if idx % 10 == 0:
        #         print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
        #     continue
        
        # Output game_info
        # if scrape_info and not game_info.empty:
        #     game_info['year'] = year
        #     append_to_csv(game_info, GAME_INFO_OUTPUT_PATH)
        
        # # Output game_stats (keep all team information)
        # if scrape_stats and not game_stats.empty:
        #     game_stats['year'] = year
        #     append_to_csv(game_stats, GAME_STATS_OUTPUT_PATH)
        
        # if the game_id was in error file, remove it now that we have valid data
        mark_game_as_valid(game_id)
        existing_ids.add(game_id)
        games_scraped += 1
        
        if idx % 10 == 0:
            print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved")
    
    if games_scraped > 0:
        print(f"    Successfully scraped and saved {games_scraped} games")
    else:
        print(f"    No game data collected for {year}")

    if error_ids_count > 0:
        print(f"    Saved {error_ids_count} error game IDs to: {str(ERROR_IDS_PATH)}")
    
    return games_scraped


def scrape_game_data_for_season(year: int, existing_ids: Set[str]) -> int:
    """
    Scrape game data for all games in a season based on SCRAPE_MODE.
    
    Modes:
    - 'GAME_INFO': Scrapes only game_info, outputs to game_info.csv
    - 'GAME_STATS': Scrapes only game_stats, outputs to game_stats.csv
    
    Returns # of games scraped.
    """

    scrape_info = SCRAPE_MODE == 'GAME_INFO'
    scrape_stats = SCRAPE_MODE == 'GAME_STATS'
    
    print(f"\n{'='*70}")
    print(f"Scraping {SCRAPE_MODE} for {year} season ({year-1}-{str(year)[-2:]})")
    print(f"{'='*70}")
    
    game_ids = get_all_game_ids_for_season(year)
    
    # filter out already scraped games
    new_game_ids = [gid for gid in game_ids if gid not in existing_ids]
    
    if len(new_game_ids) < len(game_ids):
        print(f"    Skipping {len(game_ids) - len(new_game_ids)} already scraped games")
    
    if not new_game_ids:
        print(f"All games already scraped for {year}")
        return 0
    
    print(f"    Scraping {len(new_game_ids)} new games...")
    
    games_scraped = 0
    error_ids_count = 0
    
    for idx, game_id in enumerate(new_game_ids, 1):
        game_info = pd.DataFrame()
        game_stats = pd.DataFrame()
        info_error = False
        stats_error = False
        
        # fetch game info if needed
        if scrape_info:
            game_info, info_error = get_game_info_safe(game_id)
            time.sleep(API_DELAY)
        
        # fetch game stats if needed
        if scrape_stats:
            game_stats, stats_error = get_game_stats_safe(game_id)
            time.sleep(API_DELAY)
        
        if info_error or stats_error:
            # Update error file with error flags
            update_error_game_ids(game_id, year, is_game_info_error=info_error, is_game_stats_error=stats_error)
            error_ids_count += 1
            
            if idx % 10 == 0:
                print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
            continue
        
        # Perform basic validation
        if scrape_info and game_info.empty:
            update_error_game_ids(game_id, year, is_game_info_error=True, is_game_stats_error=stats_error)
            error_ids_count += 1
            if idx % 10 == 0:
                print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
            continue
        
        if scrape_stats and game_stats.empty:
            update_error_game_ids(game_id, year, is_game_info_error=info_error, is_game_stats_error=True)
            error_ids_count += 1
            if idx % 10 == 0:
                print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved, {error_ids_count} errors")
            continue
        
        # Output game_info
        if scrape_info and not game_info.empty:
            game_info['year'] = year
            append_to_csv(game_info, GAME_INFO_OUTPUT_PATH)
        
        # Output game_stats (keep all team information)
        if scrape_stats and not game_stats.empty:
            game_stats['year'] = year
            append_to_csv(game_stats, GAME_STATS_OUTPUT_PATH)
        
        # if the game_id was in error file, remove it now that we have valid data
        mark_game_as_valid(game_id)
        existing_ids.add(game_id)
        games_scraped += 1
        
        if idx % 10 == 0:
            print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} saved")
    
    if games_scraped > 0:
        print(f"    Successfully scraped and saved {games_scraped} games")
        if scrape_info:
            print(f"    Game Info: {GAME_INFO_OUTPUT_PATH}")
        if scrape_stats:
            print(f"    Game Stats: {GAME_STATS_OUTPUT_PATH}")
    else:
        print(f"    No game data collected for {year}")

    if error_ids_count > 0:
        print(f"    Saved {error_ids_count} error game IDs to: {str(ERROR_IDS_PATH)}")
    
    return games_scraped

def scrape_boxscores_for_season(year: int, existing_ids: Set[str]) -> int:
    """Scrape boxscore data for all games in a season."""
    print(f"\n{'='*70}")
    print(f"Scraping BOXSCORES for {year} season ({year-1}-{str(year)[-2:]})")
    print(f"{'='*70}")
    
    game_ids = get_all_game_ids_for_season(year)
    
    # filter out already scraped games
    new_game_ids = [gid for gid in game_ids if gid not in existing_ids]
    
    if len(new_game_ids) < len(game_ids):
        print(f"    Skipping {len(game_ids) - len(new_game_ids)} already scraped games")
    
    if not new_game_ids:
        print(f"    All boxscores already scraped for {year}")
        return 0
    
    print(f"    Scraping {len(new_game_ids)} new games...")
    
    games_scraped = 0
    total_players = 0
    error_ids_count = 0
    # existing_error_game_ids = get_existing_game_ids(str(ERROR_IDS_PATH))
    
    for idx, game_id in enumerate(new_game_ids, 1):
        try:
            boxscore = s.get_game_boxscore(game_id)
            time.sleep(API_DELAY)
            
            if boxscore is not None and isinstance(boxscore, pd.DataFrame) and not boxscore.empty:
                boxscore['game_id'] = game_id
                boxscore = ensure_column_order(boxscore, BOXSCORE_COLUMNS)
                append_to_csv(boxscore, BOXSCORE_OUTPUT_PATH)
                
                # if the game_id was in error file, remove it now that we have valid data
                # mark_game_as_valid(game_id)
                existing_ids.add(game_id)
                games_scraped += 1
                total_players += len(boxscore)
                
                if idx % 10 == 0:
                    print(f"    Progress: {idx}/{len(new_game_ids)} games ({idx/len(new_game_ids)*100:.1f}%) - {games_scraped} games, {total_players} players saved")
            
        except Exception as e:
            update_error_game_ids(game_id, year, is_boxscore_error=True)
            error_ids_count += 1
            continue
    
    if games_scraped > 0:
        print(f"    Successfully scraped {total_players} player records from {games_scraped} games")
    else:
        print(f"    No boxscore data collected for {year}")

    if error_ids_count > 0:
        print(f"    Saved {error_ids_count} error game IDs to: {str(ERROR_IDS_PATH)}")
    
    return games_scraped

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

    output_file = ''

    if SCRAPE_MODE == 'GAME_INFO':
        output_file = GAME_INFO_OUTPUT_PATH
        scrape_function = scrape_game_data_for_season
    elif SCRAPE_MODE == 'GAME_STATS':
        output_file = GAME_STATS_OUTPUT_PATH
        scrape_function = scrape_game_data_for_season
    elif SCRAPE_MODE == 'BOXSCORES':
        output_file = BOXSCORE_OUTPUT_PATH
        scrape_function = scrape_boxscores_for_season
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
        print(f"\n[Season {season_idx}/{total_seasons}]")
        
        try:
            # scrape season data and write to file
            games_scraped = scrape_function(year, existing_ids)
            total_games_scraped += games_scraped
        except Exception as e:
            print(f"    Error processing season {year}: {e}")
            continue
        
        if year < END_YEAR:
            time.sleep(API_DELAY)
    
    if SCRAPE_MODE == 'GAME_INFO':
        print(f"\nCleaning up output file...")
        rows_removed = remove_error_game_ids_from_output(GAME_INFO_OUTPUT_PATH, 'GAME_INFO')
        if rows_removed > 0:
            print(f"  Removed {rows_removed} rows with error game_ids from output")
    elif SCRAPE_MODE == 'GAME_STATS':
        print(f"\nCleaning up output file...")
        rows_removed = remove_error_game_ids_from_output(GAME_STATS_OUTPUT_PATH, 'GAME_STATS')
        if rows_removed > 0:
            print(f"  Removed {rows_removed} rows with error game_ids from output")
    elif SCRAPE_MODE == 'BOXSCORES':
        print(f"\nCleaning up output file...")
        rows_removed = remove_error_game_ids_from_output(BOXSCORE_OUTPUT_PATH, 'BOXSCORES')
        if rows_removed > 0:
            print(f"  Removed {rows_removed} rows with error game_ids from output")
    
    print(f"\n{'='*70}")
    print("SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"Mode: {SCRAPE_MODE}")
    if SCRAPE_MODE == 'GAME_INFO':
        print(f"Output file: {GAME_INFO_OUTPUT_PATH}")
    elif SCRAPE_MODE == 'GAME_STATS':
        print(f"Output file: {GAME_STATS_OUTPUT_PATH}")
    elif SCRAPE_MODE == 'BOXSCORES':
        print(f"Output file: {BOXSCORE_OUTPUT_PATH}")
    print(f"Total games scraped: {total_games_scraped}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if SCRAPE_MODE == 'GAME_INFO':
        print(f"\nOutput file:")
        print(f"  - {GAME_INFO_OUTPUT_PATH}")
        if os.path.isfile(GAME_INFO_OUTPUT_PATH):
            try:
                game_info_df = pd.read_csv(GAME_INFO_OUTPUT_PATH)
                print(f"\nGame Info statistics:")
                print(f"  Total rows: {len(game_info_df):,}")
                if 'game_id' in game_info_df.columns:
                    print(f"  Unique games: {game_info_df['game_id'].nunique():,}")
            except Exception as e:
                print(f"  Could not read game_info statistics: {e}")
    elif SCRAPE_MODE == 'GAME_STATS':
        print(f"\nOutput file:")
        print(f"  - {GAME_STATS_OUTPUT_PATH}")
        if os.path.isfile(GAME_STATS_OUTPUT_PATH):
            try:
                game_stats_df = pd.read_csv(GAME_STATS_OUTPUT_PATH)
                print(f"\nGame Stats statistics:")
                print(f"  Total rows: {len(game_stats_df):,}")
                if 'game_id' in game_stats_df.columns:
                    print(f"  Unique games: {game_stats_df['game_id'].nunique():,}")
            except Exception as e:
                print(f"  Could not read game_stats statistics: {e}")
    elif SCRAPE_MODE == 'BOXSCORES':
        print(f"\nOutput file:")
        print(f"  - {BOXSCORE_OUTPUT_PATH}")
        if os.path.isfile(BOXSCORE_OUTPUT_PATH):
            try:
                final_df = pd.read_csv(BOXSCORE_OUTPUT_PATH)
                print(f"\nFinal dataset statistics:")
                print(f"  Total rows: {len(final_df):,}")
                if 'game_id' in final_df.columns:
                    print(f"  Unique games: {final_df['game_id'].nunique():,}")
            except Exception as e:
                print(f"  Could not read final statistics: {e}")
    
    print(f"\n{'='*70}\n")

if __name__ == "__main__":

    # print(s.get_game_stats('233402870'))

    # print(s.get_game_stats('243562413'))
    run_scraper()