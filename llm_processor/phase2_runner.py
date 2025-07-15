import os
import json
import re
import glob
from pathlib import Path
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv
import concurrent.futures
import threading
import logging
import sqlite3 # Import sqlite3
import sys # Import sys to get CLI arguments

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables once at the start of the script
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Thread-local storage for OpenAI client
_thread_local = threading.local()

# --- Database Configuration ---
DB_PATH = "data/earnings_insights.db"
RAW_TABLE_NAME = "earnings_raw_llm" # Table for raw LLM outputs

# Function to get OpenAI client for current thread
def get_openai_client():
    if not hasattr(_thread_local, "openai_client"):
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        _thread_local.openai_client = OpenAI(api_key=api_key)
    return _thread_local.openai_client

def init_db():
    """Initializes the SQLite database and creates the raw LLM output table."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {RAW_TABLE_NAME} (
            file TEXT PRIMARY KEY,
            ticker TEXT,
            quarter TEXT,
            summary TEXT,
            eps TEXT,
            revenue TEXT,
            guidance TEXT,
            key_risks TEXT, -- Stored as JSON string
            ceo_quote TEXT,
            raw_insights_json TEXT -- Store the full raw insights JSON as text
        )
    ''')
    conn.commit()
    conn.close()
    logger.info(f"Database {DB_PATH} and table {RAW_TABLE_NAME} initialized.")

def get_processed_files_from_db():
    """Retrieves a set of already processed files from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT file FROM {RAW_TABLE_NAME}")
    processed = {row[0] for row in cursor.fetchall()}
    conn.close()
    return processed

SUMMARY_PROMPT_TEMPLATE = '''
You are a financial analyst assistant. Read the following earnings call transcript and summarize it in 5-7 sentences, highlighting:
- Key financial metrics (e.g. EPS, revenue)
- Forward guidance
- Major product or strategy updates
- Sentiment or tone of executives

Transcript:
{transcript}
'''

STRUCTURE_PROMPT_TEMPLATE = '''
Extract the following fields from this earnings call transcript and return them as a JSON object:
- eps
- revenue
- guidance
- key_risks
- ceo_quote

Example:
{{
  "eps": "2.15",
  "revenue": "123.9B",
  "guidance": "Revenue growth expected in Q2",
  "key_risks": ["foreign exchange volatility", "supply chain issues"],
  "ceo_quote": "We’re optimistic about the future and focused on innovation."
}}

Transcript:
{transcript}

Only return a valid JSON object.
'''

def process_single_file(file_path):
    client = get_openai_client()
    file_name = Path(file_path).name
    try:
        with open(file_path) as f:
            record = json.load(f)
            transcript = record.get("text") or record.get("transcript")

        if not transcript:
            logger.warning(f"No transcript text found for {file_name}. Skipping.")
            return {"status": "skipped", "file": file_name, "error": "No transcript text found."}

        truncated_transcript = transcript[:8000]

        summary_prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript=truncated_transcript)
        summary_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": summary_prompt}],
            timeout=60
        )
        summary = summary_resp.choices[0].message.content.strip()

        structure_prompt = STRUCTURE_PROMPT_TEMPLATE.format(transcript=truncated_transcript)
        structure_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": structure_prompt}],
            timeout=60
        )
        structured_text = structure_resp.choices[0].message.content.strip()

        structured = {}
        try:
            structured = json.loads(structured_text)
        except json.JSONDecodeError:
            logger.debug(f"GPT-4o returned unstructured output for {file_name}. Attempting regex fallback...")
            try:
                eps_match = re.search(r'"eps"\s*:\s*"([^"]+)"', structured_text)
                revenue_match = re.search(r'"revenue"\s*:\s*"([^"]+)"', structured_text)
                guidance_match = re.search(r'"guidance"\s*:\s*"([^"]+)"', structured_text)
                risks_match = re.search(r'"key_risks"\s*:\s*\[(.*?)\]', structured_text, re.DOTALL)
                quote_match = re.search(r'"ceo_quote"\s*:\s*"([^"]+)"', structured_text)

                if eps_match: structured["eps"] = eps_match.group(1)
                if revenue_match: structured["revenue"] = revenue_match.group(1)
                if guidance_match: structured["guidance"] = guidance_match.group(1)
                if risks_match:
                    try:
                        structured["key_risks"] = json.loads(f'[{risks_match.group(1)}]')
                    except json.JSONDecodeError:
                        structured["key_risks"] = [r.strip('" ') for r in risks_match.group(1).split(",") if r.strip()]
                if quote_match: structured["ceo_quote"] = quote_match.group(1)
            except Exception as e:
                logger.error(f"Regex fallback also failed for {file_name}: {e}", exc_info=True)
                return {"status": "failed", "file": file_name, "error": f"Regex fallback also failed: {e}"}
        except Exception as e:
            logger.error(f"Unexpected error parsing structured text for {file_name}: {e}", exc_info=True)
            return {"status": "failed", "file": file_name, "error": f"Unexpected error parsing structured text: {e}"}

        # Prepare record for database insertion
        output_record = {
            "file": file_name,
            "ticker": record.get("ticker", "UNKNOWN_TICKER"),
            "quarter": record.get("quarter", "UNKNOWN_QUARTER"),
            "summary": summary,
            "eps": structured.get("eps"),
            "revenue": structured.get("revenue"),
            "guidance": structured.get("guidance"),
            "key_risks": json.dumps(structured.get("key_risks")), # Store list as JSON string
            "ceo_quote": structured.get("ceo_quote"),
            "raw_insights_json": json.dumps(structured) # Store the full insights dict as JSON string
        }

        return {"status": "success", "record": output_record}

    except Exception as e:
        logger.error(f"Failed to process {file_name}: {e}", exc_info=True)
        return {"status": "failed", "file": file_name, "error": str(e)}

# --- Main execution with concurrency ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("❌ Please provide the target ticker as a command-line argument.")
        logger.info("Usage: python llm_processor/phase2_runner.py <TICKER_SYMBOL>")
        sys.exit(1)

    TARGET_TICKER = sys.argv[1].upper()
    RAW_DIR = f"data/raw_{TARGET_TICKER.lower()}" # Dynamic raw directory

    init_db() # Initialize the database and table

    files = sorted(glob.glob(f"{RAW_DIR}/*.json"))
    processed_files_db = get_processed_files_from_db() # Get processed files from DB

    files_to_process = [f for f in files if Path(f).name not in processed_files_db]
    logger.info(f"🧹 Skipping {len(processed_files_db)} already-processed transcripts (from DB). Processing {len(files_to_process)} new ones for {TARGET_TICKER}...")

    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 2)) # Default to 2 for safety with OpenAI limits

    if not files_to_process:
        logger.info(f"No new files to process for {TARGET_TICKER}. Exiting.")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_file = {executor.submit(process_single_file, file_path): file_path for file_path in files_to_process}

            conn = sqlite3.connect(DB_PATH) # Open connection for writing results
            cursor = conn.cursor()
            for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(files_to_process), desc="Processing Transcripts"):
                result = future.result()
                if result["status"] == "success":
                    record_data = result["record"]
                    try:
                        cursor.execute(f'''
                            INSERT OR REPLACE INTO {RAW_TABLE_NAME} (
                                file, ticker, quarter, summary, eps, revenue, guidance, key_risks, ceo_quote, raw_insights_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            record_data["file"], record_data["ticker"], record_data["quarter"],
                            record_data["summary"], record_data["eps"], record_data["revenue"],
                            record_data["guidance"], record_data["key_risks"], record_data["ceo_quote"],
                            record_data["raw_insights_json"]
                        ))
                        conn.commit()
                    except sqlite3.Error as db_err:
                        logger.error(f"❌ Database error saving {record_data['file']}: {db_err}", exc_info=True)
                elif result["status"] == "skipped":
                    logger.info(f"Skipped {result['file']}: {result['error']}")
                else:
                    logger.error(f"Processing failed for {result['file']}: {result['error']}")
            conn.close() # Close connection after all writes

    logger.info(f"\n✅ All processing attempts completed for {TARGET_TICKER}.")
    logger.info(f"Results saved to database {DB_PATH} in table {RAW_TABLE_NAME}. Check logs for any errors or warnings.")