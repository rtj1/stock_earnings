import os
import shutil
import glob
import sys # Import sys to access command-line arguments
import logging

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SOURCE_DIR = "data/raw"
DEST_DIR_PREFIX = "data/raw_" # Prefix for dynamic destination directory

def run_extraction(ticker: str):
    """
    Extracts transcripts for a given ticker from SOURCE_DIR to a ticker-specific DEST_DIR.
    """
    if not ticker:
        logger.error("❌ Ticker not provided. Usage: python extract_ticker.py <TICKER_SYMBOL>")
        sys.exit(1)

    DEST_DIR = f"{DEST_DIR_PREFIX}{ticker.lower()}" # e.g., data/raw_aapl
    os.makedirs(DEST_DIR, exist_ok=True)

    # Use a pattern that matches the specific ticker
    ticker_files = glob.glob(f"{SOURCE_DIR}/{ticker.upper()}_*.json")

    logger.info(f"Starting extraction for {ticker.upper()}. Found {len(ticker_files)} files in {SOURCE_DIR}.")

    if not ticker_files:
        logger.warning(f"No {ticker.upper()} files found in {SOURCE_DIR}. Ensure phase1_loader.py has run.")
        return # Exit gracefully if no files found

    copied_count = 0
    for f in ticker_files:
        dest = os.path.join(DEST_DIR, os.path.basename(f))
        try:
            shutil.copy(f, dest)
            copied_count += 1
            logger.info(f"✅ Copied: {os.path.basename(f)} to {DEST_DIR}")
        except Exception as e:
            logger.error(f"❌ Failed to copy {os.path.basename(f)}: {e}", exc_info=True)

    logger.info(f"✅ All {copied_count} {ticker.upper()} transcripts extraction attempt completed to {DEST_DIR}.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("❌ Please provide a ticker symbol as a command-line argument.")
        logger.info("Usage: python scripts/extract_ticker.py <TICKER_SYMBOL>")
        sys.exit(1)

    TARGET_TICKER = sys.argv[1].upper() # Get ticker from CLI, convert to uppercase
    run_extraction(TARGET_TICKER)