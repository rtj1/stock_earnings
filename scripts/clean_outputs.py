import json
import logging
import sqlite3
import os

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Database Configuration ---
DB_PATH = "data/earnings_insights.db"
RAW_TABLE_NAME = "earnings_raw_llm"
CLEANED_TABLE_NAME = "earnings_cleaned_llm"

BAD_PHRASES = [
    "Please provide the content",
    "Certainly! Please provide",
    "I'm sorry, but you need to",
    "As an AI language model",
    "I cannot fulfill this request",
    "I lack the ability to",
    "I do not have access to real-time",
]

def is_valid(record):
    summary = record.get("summary", "").lower()
    if any(phrase.lower() in summary for phrase in BAD_PHRASES):
        return False
    return True

def init_cleaned_db_table():
    """Initializes the SQLite database and creates the cleaned LLM output table."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {CLEANED_TABLE_NAME} (
            file TEXT PRIMARY KEY,
            ticker TEXT,
            quarter TEXT,
            summary TEXT,
            eps TEXT,
            revenue TEXT,
            guidance TEXT,
            key_risks TEXT, -- Stored as JSON string
            ceo_quote TEXT,
            raw_insights_json TEXT, -- Store the full raw insights JSON as text
            cleaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info(f"Database {DB_PATH} and table {CLEANED_TABLE_NAME} initialized.")

logger.info(f"Starting cleaning process. Reading from {RAW_TABLE_NAME} and writing to {CLEANED_TABLE_NAME} in {DB_PATH}.")

if __name__ == "__main__":
    init_cleaned_db_table()

    conn_raw = None
    conn_cleaned = None
    try:
        conn_raw = sqlite3.connect(DB_PATH)
        cursor_raw = conn_raw.cursor()

        conn_cleaned = sqlite3.connect(DB_PATH)
        cursor_cleaned = conn_cleaned.cursor()

        # Select all records from the raw table that haven't been cleaned yet (or re-clean all)
        # For simplicity, we'll re-clean all records from raw table and replace in cleaned table
        cursor_raw.execute(f"SELECT * FROM {RAW_TABLE_NAME}")
        raw_records = cursor_raw.fetchall()

        cleaned_count = 0
        processed_count = 0

        # Get column names from cursor description
        col_names = [description[0] for description in cursor_raw.description]

        for row in raw_records:
            processed_count += 1
            record_dict = dict(zip(col_names, row))

            # Convert key_risks and raw_insights_json back to Python objects for validation
            # and then re-serialize for cleaned table if needed
            if record_dict.get("key_risks"):
                try:
                    record_dict["key_risks"] = json.loads(record_dict["key_risks"])
                except json.JSONDecodeError:
                    record_dict["key_risks"] = [] # Default to empty list if malformed
            if record_dict.get("raw_insights_json"):
                try:
                    record_dict["raw_insights_json"] = json.loads(record_dict["raw_insights_json"])
                except json.JSONDecodeError:
                    record_dict["raw_insights_json"] = {} # Default to empty dict if malformed

            if is_valid(record_dict):
                try:
                    cursor_cleaned.execute(f'''
                        INSERT OR REPLACE INTO {CLEANED_TABLE_NAME} (
                            file, ticker, quarter, summary, eps, revenue, guidance, key_risks, ceo_quote, raw_insights_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        record_dict["file"], record_dict["ticker"], record_dict["quarter"],
                        record_dict["summary"], record_dict["eps"], record_dict["revenue"],
                        record_dict["guidance"], json.dumps(record_dict["key_risks"]), # Re-serialize
                        record_dict["ceo_quote"], json.dumps(record_dict["raw_insights_json"]) # Re-serialize
                    ))
                    conn_cleaned.commit()
                except sqlite3.Error as db_err:
                    logger.error(f"❌ Database error saving cleaned record {record_dict['file']}: {db_err}", exc_info=True)
            else:
                cleaned_count += 1
                logger.warning(f"Cleaned (skipped) entry {record_dict.get('file')} due to invalid summary content.")

    except sqlite3.Error as e:
        logger.critical(f"A critical SQLite error occurred during cleaning: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"A critical unexpected error occurred during cleaning: {e}", exc_info=True)
    finally:
        if conn_raw:
            conn_raw.close()
        if conn_cleaned:
            conn_cleaned.close()

    logger.info(f"✅ Finished cleaning. Processed {processed_count} entries. Cleaned (skipped/filtered) {cleaned_count} bad entries.")