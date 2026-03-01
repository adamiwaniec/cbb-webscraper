import os
import pandas as pd
import time
from typing import Any, Optional
import sys
from pathlib import Path
import logging

from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import numpy as np

_this_dir = str(Path(__file__).parent)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
from config import *

BETIQ_URL = 'https://betiq.teamrankings.com/college-basketball/betting-trends/custom-trend-tool/?min_season={}&max_season={}'

# Set up logging
logging.basicConfig(
    level=logging.WARNING,  # Default to WARNING, will be changed based on LOGGING_ENABLED
    format='%(message)s',  # Simpler format
    handlers=[
        # logging.FileHandler('scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global driver instance
driver = None

# ============================================================================
# CONFIGURATION MACROS - Tune these to customize scraping behavior
# ============================================================================

# Enable detailed logging: True (verbose logging), False (print statements only)
LOGGING_ENABLED = True

# Seasons to scrape (format: "YYYY-YYYY")
MIN_SEASON = "2024-2025"  # Start season
MAX_SEASON = "2024-2025"  # End season (optional, mostly for reference)

# Delay between requests (in seconds)
# Format: (min_delay, max_delay) - random delay between these values
API_DELAY_RANGE = (0.3, 0.6)

# Maximum pages to scrape per run
# Set to None to scrape all pages
MAX_PAGES_TO_SCRAPE = None

# Rows per page display mode
# Options: 25, 50, 100
ROWS_PER_PAGE = 100

#output file path
OUTPUT_CSV_FILE = BETIQ_SPORTSBOOK_LINES_PATH

#no browser window
HEADLESS_MODE = True

# request timeout in seconds
REQUEST_TIMEOUT = 10

# ============================================================================


def _configure_logging() -> None:
    """Configure logging based on LOGGING_ENABLED setting."""
    if LOGGING_ENABLED:
        logger.setLevel(logging.INFO)
        for handler in logger.handlers:
            handler.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)
        for handler in logger.handlers:
            handler.setLevel(logging.WARNING)


def scrape_betting_trends_single_page(url: str, wait_time: int = 10) -> pd.DataFrame:
    """Scrape data from current page in browser."""
    try:
        logger.debug(f"Waiting for table...")
        wait = WebDriverWait(driver, wait_time)
        table_rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr")))
        logger.debug(f"Found {len(table_rows)} tr elements")
        
        time.sleep(2)
        soup = bs(driver.page_source, 'html.parser')
        tables = soup.find_all('table')
        
        # Find table with 'Date', 'Team', 'Opponent' columns
        best_table = None
        best_row_count = 0
        best_idx = -1
        
        for idx, table in enumerate(tables):
            thead = table.find('thead')
            headers = []
            if thead:
                header_row = thead.find('tr')
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
            else:
                rows = table.find_all('tr')[1:] if headers else table.find_all('tr')
            
            if len(rows) > best_row_count and 'Date' in headers and 'Team' in headers:
                best_table = table
                best_row_count = len(rows)
                best_idx = idx
        
        if best_table:
            return _extract_table_data(best_table)
        else:
            return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error extracting page: {e}")
        return pd.DataFrame()


def _extract_table_data(table) -> pd.DataFrame:
    """Extract data from a BeautifulSoup table element."""
    headers = []
    thead = table.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
    
    tbody = table.find('tbody')
    if tbody:
        rows = tbody.find_all('tr')
    else:
        rows = table.find_all('tr')[1:] if headers else table.find_all('tr')
    
    data = []
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if cells:
            if headers and len(headers) == len(cells):
                row_data = {headers[i]: cell.get_text(strip=True) for i, cell in enumerate(cells)}
            else:
                row_data = {f"col_{i}": cell.get_text(strip=True) for i, cell in enumerate(cells)}
            data.append(row_data)
    
    logger.debug(f"Extracted {len(data)} rows")
    return pd.DataFrame(data)


def _close_banners(driver) -> None:
    """Close common banners and popups (cookie, consent, etc)."""
    banner_selectors = [
        "#onetrust-policy-text",
        "#onetrust-close-btn-container button",
        ".onetrust-close-btn-handler",
        "[data-testid='cookie-accept-button']",
        "button[class*='accept']",
        ".cookie-banner button",
    ]
    
    for selector in banner_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                for elem in elements:
                    try:
                        driver.execute_script("arguments[0].style.display = 'none';", elem)
                    except:
                        pass
        except:
            pass


def _set_rows_per_page(driver, rows: int) -> bool:
    """Click button to set rows displayed per page."""
    try:
        logger.info(f"Setting rows to {rows}...")
        string_rows = str(rows)
        
        # The page uses a SELECT dropdown for rows per page
        # Try to find and change the select element directly
        try:
            select_elem = driver.find_element(By.NAME, "custom-filter-table_length")
            logger.debug(f"Found select element for rows per page")
            
            # Select the option with value = rows
            option_xpath = f"//select[@name='custom-filter-table_length']//option[@value='{rows}']"
            option = driver.find_element(By.XPATH, option_xpath)
            driver.execute_script("arguments[0].selected = true;", option)
            
            # Trigger change event
            driver.execute_script("""
                var event = new Event('change', { bubbles: true });
                arguments[0].dispatchEvent(event);
            """, select_elem)
            
            time.sleep(3)  # Wait for table to reload
            logger.info(f"Set to {rows} rows per page via select dropdown")
            return True
        except Exception as e:
            logger.debug(f"Select dropdown method failed: {e}")
        
        # Fallback: try other common selectors
        selectors = [
            (f"a[data-val='{rows}']", "CSS"),
            (f"button[data-val='{rows}']", "CSS"),
            (f"//a[contains(text(), '{string_rows}')]", "XPath"),
        ]
        
        for selector, sel_type in selectors:
            try:
                if sel_type == "XPath":
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if elements:
                    logger.debug(f"Found selector: {selector}")
                    driver.execute_script("arguments[0].click();", elements[0])
                    time.sleep(2)
                    logger.info(f"Set to {rows} rows per page")
                    return True
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
        
        logger.warning(f"Could not set rows to {rows}. Continuing with default.")
        return False
        
    except Exception as e:
        logger.error(f"Error setting rows: {e}")
        return False


def _find_next_button(driver) -> Optional[Any]:
    """Find next pagination button."""
    selectors = [
        "a.next",
        "button.next",
        "a[aria-label*='next']",
        "button[aria-label*='next']",
        "a[rel='next']",
        "li.next a",
    ]
    
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                logger.debug(f"Found next button: {selector}")
                return elements[0]
        except:
            pass
    
    return None


def _is_button_disabled(button) -> bool:
    """Check if button is disabled."""
    try:
        if button.get_attribute('disabled'):
            return True
        if button.get_attribute('aria-disabled') == 'true':
            return True
        classes = button.get_attribute('class') or ''
        if 'disabled' in classes.lower():
            return True
        return False
    except:
        return False

# return entire data frame and number of new rows scraped as two variables
def scrape_all_pages(base_url: str, output_file: str = None, 
                     max_pages: Optional[int] = None):
    """Scrape all pages by clicking pagination."""
    global driver
    
    # Use config values if not provided
    if output_file is None:
        output_file = OUTPUT_CSV_FILE
    if max_pages is None:
        max_pages = MAX_PAGES_TO_SCRAPE
    
    # Initialize driver
    options = webdriver.ChromeOptions()
    if HEADLESS_MODE:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    all_data = []
    page_count = 0
    combined_df = pd.DataFrame()
    seen_rows = set()  # Track unique rows by tuple
    new_rows_total = 0
    
    # Load existing data if file exists to prevent duplicates
    if os.path.exists(output_file):
        try:
            # Force all columns to string type for consistent comparison
            combined_df = pd.read_csv(output_file, dtype=str)
            # Replace NaN strings with empty strings for consistency
            combined_df = combined_df.fillna('')
            # Build set of existing rows for O(1) lookup
            for _, row in combined_df.iterrows():
                row_tuple = tuple(row.values)
                seen_rows.add(row_tuple)
            logger.info(f"Loaded existing file: {len(combined_df)} rows")
        except Exception as e:
            logger.warning(f"Could not load existing file: {e}")
            combined_df = pd.DataFrame()
    
    try:
        logger.info(f"Loading: {base_url}")
        driver.get(base_url)
        time.sleep(3)
        
        _close_banners(driver)
        time.sleep(1)
        
        # Set rows per page
        logger.info(f"Config: {ROWS_PER_PAGE} rows/page, {API_DELAY_RANGE[0]}-{API_DELAY_RANGE[1]}s delay")
        rows_set = _set_rows_per_page(driver, ROWS_PER_PAGE)
        if rows_set:
            time.sleep(2)
        
        print(f"Scraping... (100 rows/page, {API_DELAY_RANGE[0]}-{API_DELAY_RANGE[1]}s delay)")
        print("Progress:")
        
        while True:
            page_count += 1
            logger.info(f"\nPage {page_count}")
            
            df = scrape_betting_trends_single_page(base_url)
            
            if not df.empty:
                logger.info(f"Got {len(df)} rows")
                
                # Convert all to string and replace NaN/nan strings with empty strings
                df = df.astype(str)
                df = df.replace('nan', '')
                
                # Only add rows we haven't seen before
                new_rows = []
                for _, row in df.iterrows():
                    row_tuple = tuple(row.values)
                    if row_tuple not in seen_rows:
                        new_rows.append(row)
                        seen_rows.add(row_tuple)
                
                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    combined_df = pd.concat([combined_df, new_df], ignore_index=True)
                    combined_df.to_csv(output_file, index=False)
                    logger.info(f"Added {len(new_rows)} new rows, {len(combined_df)} total")
                else:
                    logger.info(f"All {len(df)} rows were duplicates")
                
                new_rows_total += len(new_rows)
                
                # Print progress every page
                print(f"  Page {page_count}: {len(combined_df):,} rows total", end="\r")
            else:
                logger.warning("No data from page")
                print(f"  WARNING: No data on page {page_count}")
            
            if max_pages and page_count >= max_pages:
                logger.info(f"Reached max: {max_pages}")
                print()  # Clear the progress line
                print(f"Reached maximum pages: {max_pages}")
                break
            
            next_button = _find_next_button(driver)
            if not next_button or _is_button_disabled(next_button):
                logger.info("No more pages")
                print()  # Clear the progress line
                print(f"Reached end of data")
                break
            
            try:
                print()  # Clear the progress line first
                logger.info(f"Clicking to page {page_count + 1}...")
                _close_banners(driver)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", next_button)
                
                delay = np.random.uniform(API_DELAY_RANGE[0], API_DELAY_RANGE[1])
                logger.info(f"Waiting {delay:.1f}s...")
                time.sleep(delay)
                
                wait = WebDriverWait(driver, REQUEST_TIMEOUT)
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr")))
                time.sleep(2)
            except Exception as e:
                logger.error(f"Click error: {e}")
                print(f"\nERROR: Failed to click next page: {e}")
                break
        
        logger.info(f"Complete: {page_count} pages")
        logger.info(f"Total: {len(combined_df)} rows (duplicates removed)")
        logger.info(f"Config: {ROWS_PER_PAGE}/page, {MIN_SEASON}-{MAX_SEASON}")
        logger.info(f"Saved to: {output_file}")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\nERROR: {e}")
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Partial save: {len(combined_df)} rows")
            print(f"Partial save: {len(combined_df)} rows")
    
    finally:
        driver.quit()
        logger.info("Browser closed")
    
    return combined_df, new_rows_total


# =============================================================================
# ODDSHARVESTER CONFIGURATION
# =============================================================================

OH_SPORT = "basketball"
OH_LEAGUE = "ncaa"
OH_HISTORICAL_SEASONS = [
    "2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"
]

# Build market value strings for common spread and total lines
# Spreads: -25.5 to +25.5 (half-point only, no zero)
OH_SPREAD_MARKETS = []
for i in range(-25, 0):
    OH_SPREAD_MARKETS.append(f"asian_handicap_games_{i}_5_games")
# +0.5 through +25.5
for i in range(0, 26):
    OH_SPREAD_MARKETS.append(f"asian_handicap_games_+{i}_5_games")

# Totals: 120.5 to 180.5 (half-point only)
OH_TOTAL_MARKETS = [f"over_under_games_{i}_5" for i in range(120, 181)]

# All markets combined (moneyline + spreads + totals) — used for historical scraping
OH_ALL_MARKETS = ["home_away"] + OH_SPREAD_MARKETS + OH_TOTAL_MARKETS

# Upcoming-only markets: just moneyline for fast scraping.
# OddsHarvester has difficulty navigating spread/total tabs on upcoming NCAAB match pages,
# causing excessive timeouts. Moneyline is the primary market used for predictions.
OH_UPCOMING_MARKETS = ["home_away"]


# =============================================================================
# ODDSHARVESTER SHARED HELPERS
# =============================================================================

def decimal_to_american(decimal_odds: float) -> int:
    """Convert European decimal odds to American moneyline odds."""
    if decimal_odds is None or decimal_odds <= 1.0:
        return 0
    if decimal_odds >= 2.0:
        return int(round((decimal_odds - 1) * 100))
    else:
        return int(round(-100 / (decimal_odds - 1)))


def american_to_decimal(american_odds: int) -> float:
    """Convert American moneyline odds to European decimal odds."""
    if american_odds >= 100:
        return round(1.0 + american_odds / 100, 4)
    elif american_odds <= -100:
        return round(1.0 + 100 / abs(american_odds), 4)
    return 0.0


def _parse_odds_value(raw: str) -> tuple:
    """
    Parse an odds string that could be decimal ('1.63') or American ('-159', '+135').

    Returns (decimal_odds, american_odds) tuple.
    """
    if not raw:
        return (0.0, 0)
    raw = raw.strip()
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return (0.0, 0)

    # Detect format: American odds are integers >= 100 or <= -100
    # Decimal odds are always > 1.0 and typically < 100
    if val >= 100 or val <= -100:
        # American format
        american = int(val)
        decimal = american_to_decimal(american)
        return (decimal, american)
    elif val > 1.0:
        # Decimal format
        return (val, decimal_to_american(val))
    else:
        return (0.0, 0)


def _parse_oh_matches(matches: list, markets_requested: list) -> list:
    """
    Parse OddsHarvester match results into flat rows.

    Each match dict has keys like 'home_away_market', 'over_under_games_140_5_market',
    'asian_handicap_games_-5_5_games_market', etc. Each market value is a list of
    bookie dicts with odds labels as keys.

    Returns list of dicts with standardized columns.
    """
    all_rows = []

    # If matches is a DataFrame (from CSV), convert to list of dicts with parsed market columns
    if isinstance(matches, pd.DataFrame):
        records = matches.to_dict(orient='records')
    else:
        records = matches

    for match in records:
        home_team = match.get('home_team', '')
        away_team = match.get('away_team', '')
        match_date = match.get('match_date', '')
        league_name = match.get('league_name', '')
        home_score = match.get('home_score', None)
        away_score = match.get('away_score', None)
        match_link = match.get('match_link', '')

        base_row = {
            'match_date': match_date,
            'home_team': home_team,
            'away_team': away_team,
            'league_name': league_name,
            'home_score': home_score,
            'away_score': away_score,
            'match_link': match_link,
        }

        for market_val in markets_requested:
            market_key = f"{market_val}_market"
            market_data = match.get(market_key, None)

            # If market_data is a string (from CSV), parse it as a list of dicts
            if isinstance(market_data, str):
                import ast
                try:
                    market_data = ast.literal_eval(market_data)
                except Exception:
                    continue

            if not market_data or not isinstance(market_data, list):
                continue

            for bookie in market_data:
                bookmaker = bookie.get('bookmaker_name', '')

                if market_val == "home_away":
                    # Moneyline: keys '1' (home) and '2' (away)
                    # Odds may be decimal ('1.63') or American ('-159')
                    home_dec, home_am = _parse_odds_value(str(bookie.get('1', '')))
                    away_dec, away_am = _parse_odds_value(str(bookie.get('2', '')))
                    if home_dec <= 1.0 or away_dec <= 1.0:
                        continue
                    all_rows.append({
                        **base_row,
                        'market_type': 'moneyline',
                        'line_value': None,
                        'home_odds_dec': home_dec,
                        'away_odds_dec': away_dec,
                        'home_odds_american': home_am,
                        'away_odds_american': away_am,
                        'over_odds_dec': None,
                        'under_odds_dec': None,
                        'bookmaker_name': bookmaker,
                    })

                elif market_val.startswith("over_under_games_"):
                    # Total: keys 'odds_over' and 'odds_under'
                    line_str = market_val.replace("over_under_games_", "").replace("_", ".")
                    try:
                        line_val = float(line_str)
                    except (ValueError, TypeError):
                        continue
                    over_dec, _ = _parse_odds_value(str(bookie.get('odds_over', '')))
                    under_dec, _ = _parse_odds_value(str(bookie.get('odds_under', '')))
                    if over_dec <= 1.0 or under_dec <= 1.0:
                        continue
                    all_rows.append({
                        **base_row,
                        'market_type': 'total',
                        'line_value': line_val,
                        'home_odds_dec': None,
                        'away_odds_dec': None,
                        'home_odds_american': None,
                        'away_odds_american': None,
                        'over_odds_dec': over_dec,
                        'under_odds_dec': under_dec,
                        'bookmaker_name': bookmaker,
                    })

                elif market_val.startswith("asian_handicap_games_"):
                    # Spread: keys 'handicap_team_1' and 'handicap_team_2'
                    line_str = market_val.replace("asian_handicap_games_", "").replace("_games", "").replace("_", ".")
                    try:
                        line_val = float(line_str)
                    except (ValueError, TypeError):
                        continue
                    home_dec, home_am = _parse_odds_value(str(bookie.get('handicap_team_1', '')))
                    away_dec, away_am = _parse_odds_value(str(bookie.get('handicap_team_2', '')))
                    if home_dec <= 1.0 or away_dec <= 1.0:
                        continue
                    all_rows.append({
                        **base_row,
                        'market_type': 'spread',
                        'line_value': line_val,
                        'home_odds_dec': home_dec,
                        'away_odds_dec': away_dec,
                        'home_odds_american': home_am,
                        'away_odds_american': away_am,
                        'over_odds_dec': None,
                        'under_odds_dec': None,
                        'bookmaker_name': bookmaker,
                    })

    return all_rows


# =============================================================================
# ODDSHARVESTER SCRAPING FUNCTIONS
# =============================================================================

def scrape_upcoming_odds(day: str = "today") -> pd.DataFrame:
    """
    Scrape upcoming NCAA basketball odds from OddsPortal via OddsHarvester.

    Parameters:
        day: "today", "tomorrow", or "both"

    Returns:
        DataFrame with odds for all markets (moneyline, spread, total).
        Saves to data/sportsbook_lines_raw/oh_upcoming_odds.csv
    """

    from datetime import datetime as dt, timedelta

    # Load the pre-scraped odds CSV
    matches = pd.read_csv(OH_UPCOMING_ODDS_PATH)
    if matches.empty:
        print("  No upcoming odds found in CSV")
        return pd.DataFrame()

    # Determine target dates based on 'day' argument
    today = dt.now()
    if day == "today":
        target_dates = [today.strftime('%Y-%m-%d')]
    elif day == "tomorrow":
        target_dates = [(today + timedelta(days=1)).strftime('%Y-%m-%d')]
    elif day == "both":
        target_dates = [today.strftime('%Y-%m-%d'), (today + timedelta(days=1)).strftime('%Y-%m-%d')]
    else:
        print(f"  [ERR] Invalid day parameter: {day}. Use 'today', 'tomorrow', or 'both'.")
        return pd.DataFrame()

    
    # Filter matches by date part of match_date (ignore time)
    if 'match_date' in matches.columns:
        # Extract just the date part (YYYY-MM-DD) from match_date
        match_dates = matches['match_date'].astype(str).str[:10]
        matches = matches[match_dates.isin(target_dates)]
    else:
        print("  [ERR] match_date column not found in oh_upcoming_odds.csv")
        return pd.DataFrame()

    if matches.empty:
        print(f"  No upcoming odds found for {', '.join(target_dates)} in CSV")
        return pd.DataFrame()

    # Parse odds for all available markets
    all_rows = _parse_oh_matches(matches, OH_UPCOMING_MARKETS)
    if not all_rows:
        print("  No parseable odds data in filtered results")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    # Optionally save filtered/parsed odds for debugging
    # os.makedirs(str(SPORTSBOOK_LINES_RAW_PATH), exist_ok=True)
    # output_path = OH_UPCOMING_ODDS_PATH.replace('.csv', '_filtered.csv')
    # df.to_csv(str(output_path), index=False)

    _print_odds_summary(df)
    return df


def scrape_historical_odds(seasons: list = None) -> pd.DataFrame:
    """
    Scrape historical NCAA basketball odds from OddsPortal via OddsHarvester.

    Parameters:
        seasons: List of season strings, e.g. ["2023-2024", "2024-2025"].
                 Defaults to OH_HISTORICAL_SEASONS.

    Returns:
        DataFrame with historical odds for all markets.
        Saves to data/sportsbook_lines_raw/oh_historical_odds.csv
    """
    import asyncio

    try:
        from oddsharvester.core.scraper_app import run_scraper
        from oddsharvester.utils.command_enum import CommandEnum
    except ImportError:
        print("  [ERR] OddsHarvester not installed. Cannot scrape historical odds.")
        return pd.DataFrame()

    if seasons is None:
        seasons = OH_HISTORICAL_SEASONS

    async def _scrape_all_seasons():
        all_results = []
        for season in seasons:
            print(f"\n  Scraping historical odds for season {season}...")
            try:
                result = await run_scraper(
                    command=CommandEnum.HISTORIC,
                    sport=OH_SPORT,
                    leagues=[OH_LEAGUE],
                    season=season,
                    markets=OH_ALL_MARKETS,
                    headless=True,
                )
                if result is not None and result.success:
                    print(f"    Found {len(result.success)} matches "
                          f"({result.stats.successful} successful, "
                          f"{result.stats.failed} failed)")
                    # Tag each match with the season
                    for m in result.success:
                        m['_season'] = season
                    all_results.extend(result.success)
                else:
                    print(f"    No odds found for season {season}")
                    if result and result.failed:
                        print(f"    {len(result.failed)} URLs failed")
                if result and result.partial:
                    print(f"    {len(result.partial)} partial results")
            except Exception as e:
                print(f"    Error scraping season {season}: {e}")
        return all_results

    matches = asyncio.run(_scrape_all_seasons())

    if not matches:
        print("  No historical odds found")
        return pd.DataFrame()

    all_rows = _parse_oh_matches(matches, OH_ALL_MARKETS)

    # Add season column from tagged matches
    if all_rows:
        # Re-parse to include season - match by match_link
        link_to_season = {}
        for m in matches:
            link = m.get('match_link', '')
            if link:
                link_to_season[link] = m.get('_season', '')
        for row in all_rows:
            row['season'] = link_to_season.get(row.get('match_link', ''), '')

    if not all_rows:
        print("  No parseable odds data in historical results")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Save to file
    os.makedirs(str(SPORTSBOOK_LINES_RAW_PATH), exist_ok=True)
    output_path = OH_HISTORICAL_ODDS_PATH
    df.to_csv(str(output_path), index=False)
    print(f"\n  Saved {len(df)} historical odds rows to {output_path}")
    _print_odds_summary(df)

    return df


def _print_odds_summary(df: pd.DataFrame) -> None:
    """Print a summary of scraped odds data."""
    if df.empty:
        return
    print(f"\n  --- Odds Summary ---")
    print(f"  Total rows: {len(df)}")
    if 'market_type' in df.columns:
        for mtype, count in df['market_type'].value_counts().items():
            print(f"    {mtype}: {count} rows")
    if 'bookmaker_name' in df.columns:
        n_bookies = df['bookmaker_name'].nunique()
        print(f"  Bookmakers: {n_bookies}")
    unique_matches = df.groupby(['home_team', 'away_team', 'match_date']).ngroups
    print(f"  Unique matches: {unique_matches}")
    print(f"  -------------------")


if __name__ == "__main__":
    # url = f'https://betiq.teamrankings.com/college-basketball/betting-trends/custom-trend-tool/?min_season={MIN_SEASON}&max_season={MAX_SEASON}'

    url = BETIQ_URL.format(MIN_SEASON, MAX_SEASON)

    
    _configure_logging()
    
    print("=" * 60)
    print("Betting Trends Scraper")
    print("=" * 60)
    print(f"Rows per page: {ROWS_PER_PAGE}")
    print(f"Logging: {'ON' if LOGGING_ENABLED else 'OFF'}")
    if MAX_PAGES_TO_SCRAPE:
        print(f"Max pages: {MAX_PAGES_TO_SCRAPE}")
    print("=" * 60)
    
    logger.info(f"MIN_SEASON: {MIN_SEASON}")
    logger.info(f"API_DELAY_RANGE: {API_DELAY_RANGE}")
    logger.info(f"HEADLESS_MODE: {HEADLESS_MODE}")
    logger.info(f"Output file: {OUTPUT_CSV_FILE}")
    
    df, new_rows = scrape_all_pages(url)
    
    print("=" * 60)
    if not df.empty:
        print(f"SUCCESS: Scraped {len(df)} rows ({new_rows} new rows)")
        print(f"Columns: {len(df.columns)}")
        if 'Date' in df.columns:
            print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
        print(f"Saved to: {OUTPUT_CSV_FILE}")
    else:
        print("ERROR: No data extracted")
    print("=" * 60)
    
    logger.info(f"Final: {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"Columns: {df.columns.tolist()}")
