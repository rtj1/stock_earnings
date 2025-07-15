from fastapi import FastAPI, HTTPException
import json
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import sqlite3 # Import sqlite3

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic Models for API Responses ---
class InsightsDetail(BaseModel):
    eps: Optional[str] = None
    revenue: Optional[str] = None
    guidance: Optional[str] = None
    key_risks: Optional[List[str]] = None
    ceo_quote: Optional[str] = None

class CompanyRecordResponse(BaseModel):
    file: str
    ticker: str
    quarter: str
    summary: str
    insights: InsightsDetail # Use the InsightsDetail model here

class SummaryResponse(BaseModel):
    ticker: str
    summary: str

class InsightsOnlyResponse(BaseModel):
    ticker: str
    insights: InsightsDetail

# --- FastAPI App Setup ---
app = FastAPI(title="Earnings Insight API", version="1.0.0")

# --- Database Configuration ---
DB_PATH = "data/earnings_insights.db"
CLEANED_TABLE_NAME = "earnings_cleaned_llm"

# Global cache for data (will be populated from DB)
_data_cache: Dict[str, Dict[int, Dict[str, Any]]] = {} # ticker -> year -> quarter -> record

# --- Startup Event to Load Data from DB ---
@app.on_event("startup")
async def load_data_from_db_on_startup():
    """Loads data from the SQLite database into memory when the FastAPI application starts."""
    global _data_cache
    _data_cache = {} # Clear previous cache

    if not os.path.exists(DB_PATH):
        logger.warning(f"Database file not found at {DB_PATH}. API will return 404s for all requests.")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row # Return rows as dict-like objects
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {CLEANED_TABLE_NAME}")
        records = cursor.fetchall()

        for row in records:
            record_dict = dict(row) # Convert Row object to dictionary
            
            # Parse JSON strings back to Python objects
            if record_dict.get("key_risks"):
                try:
                    record_dict["key_risks"] = json.loads(record_dict["key_risks"])
                except json.JSONDecodeError:
                    record_dict["key_risks"] = [] # Handle malformed JSON
            else:
                record_dict["key_risks"] = [] # Ensure it's a list if None

            if record_dict.get("raw_insights_json"):
                try:
                    record_dict["insights"] = json.loads(record_dict["raw_insights_json"])
                except json.JSONDecodeError:
                    record_dict["insights"] = {} # Handle malformed JSON
            else:
                record_dict["insights"] = {} # Ensure it's a dict if None

            # Add individual insights fields to the main dict for Pydantic mapping
            record_dict["insights"]["eps"] = record_dict.get("eps")
            record_dict["insights"]["revenue"] = record_dict.get("revenue")
            record_dict["insights"]["guidance"] = record_dict.get("guidance")
            record_dict["insights"]["ceo_quote"] = record_dict.get("ceo_quote")
            record_dict["insights"]["key_risks"] = record_dict.get("key_risks") # Use the parsed list

            # Build nested cache: ticker -> year -> quarter -> record
            ticker = record_dict["ticker"].upper()
            quarter_str = record_dict["quarter"]
            try:
                q, y = quarter_str.split("_")
                year_int = int(y)
            except ValueError:
                logger.warning(f"Could not parse quarter string: {quarter_str} for ticker {ticker}. Skipping cache entry.")
                continue

            if ticker not in _data_cache:
                _data_cache[ticker] = {}
            if year_int not in _data_cache[ticker]:
                _data_cache[ticker][year_int] = {}
            _data_cache[ticker][year_int][q] = record_dict # Store the full dict

        logger.info(f"Successfully loaded {len(records)} records from {DB_PATH} into memory.")
    except sqlite3.Error as e:
        logger.critical(f"A critical SQLite error occurred during data loading: {e}", exc_info=True)
        _data_cache = {}
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred during data loading: {e}", exc_info=True)
        _data_cache = {}
    finally:
        if conn:
            conn.close()

# --- New Endpoint to List All Tickers and Quarters for Streamlit Dropdowns ---
@app.get("/tickers_quarters")
def get_all_tickers_and_quarters():
    """
    Returns a nested dictionary of all available tickers, years, and quarters,
    optimized for Streamlit dropdown population.
    { "AAPL": { 2006: ["Q1", "Q2"], 2007: ["Q1"] }, "MSFT": { 2020: ["Q3"] } }
    """
    if not _data_cache:
        logger.warning("Attempted to get tickers, but data cache is empty.")
        return {}

    # _data_cache is already in the desired ticker -> year -> quarter structure
    # We just need to convert sets to lists for JSON serialization and sort them
    output = {}
    for ticker, years_dict in _data_cache.items():
        output[ticker] = {}
        for year, quarters_dict in years_dict.items():
            output[ticker][year] = sorted(list(quarters_dict.keys())) # Get quarter keys and sort

    logger.info(f"Returning {len(output)} tickers to client for dropdowns.")
    return output

# --- API Endpoints ---
@app.get("/summary/{ticker}", response_model=SummaryResponse)
def get_summary(ticker: str):
    """
    Retrieves the summary for a given company ticker.
    This endpoint will return the summary for the most recent quarter available for the ticker.
    """
    logger.info(f"Received request for summary of ticker: {ticker}")
    ticker_data = _data_cache.get(ticker.upper())
    if not ticker_data:
        logger.warning(f"Summary for ticker '{ticker}' not found.")
        raise HTTPException(status_code=404, detail=f"Summary for ticker '{ticker}' not found.")

    # Find the most recent quarter for the given ticker
    latest_year = max(ticker_data.keys())
    latest_quarter_key = sorted(ticker_data[latest_year].keys(), key=lambda q: int(q[1:]), reverse=True)[0]
    item = ticker_data[latest_year][latest_quarter_key]

    return SummaryResponse(ticker=item["ticker"], summary=item["summary"])

@app.get("/insights/{ticker}", response_model=InsightsOnlyResponse)
def get_insights(ticker: str):
    """
    Retrieves the extracted insights for a given company ticker.
    This endpoint will return the insights for the most recent quarter available for the ticker.
    """
    logger.info(f"Received request for insights of ticker: {ticker}")
    ticker_data = _data_cache.get(ticker.upper())
    if not ticker_data:
        logger.warning(f"Insights for ticker '{ticker}' not found.")
        raise HTTPException(status_code=404, detail=f"Insights for ticker '{ticker}' not found.")

    # Find the most recent quarter for the given ticker
    latest_year = max(ticker_data.keys())
    latest_quarter_key = sorted(ticker_data[latest_year].keys(), key=lambda q: int(q[1:]), reverse=True)[0]
    item = ticker_data[latest_year][latest_quarter_key]

    return InsightsOnlyResponse(ticker=item["ticker"], insights=InsightsDetail(**item["insights"]))

@app.get("/company/{ticker}/{quarter_key}", response_model=CompanyRecordResponse)
def get_full_record(ticker: str, quarter_key: str):
    """
    Retrieves the full record (summary and insights) for a given company ticker and quarter.
    quarter_key format: Q1_2006
    """
    logger.info(f"Received request for full record of ticker: {ticker}, quarter: {quarter_key}")
    ticker_data = _data_cache.get(ticker.upper())
    if not ticker_data:
        logger.warning(f"Full record for ticker '{ticker}' not found.")
        raise HTTPException(status_code=404, detail=f"Full record for ticker '{ticker}' not found.")

    try:
        q, y = quarter_key.split("_")
        year_int = int(y)
    except ValueError:
        logger.error(f"Invalid quarter_key format: {quarter_key}")
        raise HTTPException(status_code=400, detail="Invalid quarter_key format. Expected QX_YYYY (e.g., Q1_2006).")

    if year_int in ticker_data and q in ticker_data[year_int]:
        item = ticker_data[year_int][q]
        # Ensure the insights sub-object is correctly mapped to InsightsDetail
        item_copy = item.copy() # Avoid modifying cached object directly
        item_copy["insights"] = InsightsDetail(**item_copy["insights"])
        return CompanyRecordResponse(**item_copy)
    else:
        logger.warning(f"Record for ticker '{ticker}', quarter '{quarter_key}' not found.")
        raise HTTPException(status_code=404, detail=f"Record for ticker '{ticker}', quarter '{quarter_key}' not found.")