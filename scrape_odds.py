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

sys.path.insert(0, str(Path(__file__).parent))
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
MIN_SEASON = "2002-2003"  # Start season
MAX_SEASON = "2025-2026"  # End season (optional, mostly for reference)

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
OUTPUT_CSV_FILE = CBB_SPORTSBOOK_LINES_PATH

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


def scrape_all_pages(base_url: str, output_file: str = None, 
                     max_pages: Optional[int] = None) -> pd.DataFrame:
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
    
    return combined_df


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
    
    df = scrape_all_pages(url)
    
    print("=" * 60)
    if not df.empty:
        print(f"SUCCESS: Scraped {len(df)} rows")
        print(f"Columns: {len(df.columns)}")
        if 'Date' in df.columns:
            print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
        print(f"Saved to: {OUTPUT_CSV_FILE}")
    else:
        print("ERROR: No data extracted")
    print("=" * 60)
    
    logger.info(f"Final: {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"Columns: {df.columns.tolist()}")
