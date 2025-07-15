#!/bin/sh
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration (can be overridden by Docker environment variables) ---
TARGET_TICKER="${TARGET_TICKER:-AAPL}" # Default to AAPL if not set
MAX_WORKERS="${MAX_WORKERS:-2}"       # Default to 2 if not set (adjust as needed)
DB_PATH="data/earnings_insights.db"
CLEANED_TABLE_NAME="earnings_cleaned_llm"
FASTAPI_HOST="0.0.0.0" # Listen on all interfaces inside the container
FASTAPI_PORT="8000"

echo "🚀 Starting Earnings Insight Dockerized Pipeline..."
echo "Targeting ticker: $TARGET_TICKER"
echo "Max LLM Workers: $MAX_WORKERS"

# --- Data Processing Steps ---
echo "Checking if cleaned LLM outputs exist in database..."

DB_EXISTS=false
if [ -f "$DB_PATH" ]; then
    RECORD_COUNT=$(sqlite3 -batch "$DB_PATH" "SELECT COUNT(*) FROM $CLEANED_TABLE_NAME;" 2>/dev/null || echo 0)
    if [ "$RECORD_COUNT" -gt 0 ]; then
        DB_EXISTS=true
    fi
fi

if [ "$DB_EXISTS" = true ]; then
    echo "✅ Cleaned LLM outputs in database already exist. Skipping data loading and processing."
else
    echo "⬇️ Cleaned LLM outputs in database not found or empty. Running full data pipeline."

    echo "Downloading and preparing raw data..."
    if [ ! -d "data/raw" ] || [ -z "$(ls -A data/raw 2>/dev/null)" ]; then
        python3 data_ingestion/phase1_loader.py
    else
        echo "✅ Raw data already exists in data/raw/. Skipping download."
    fi

    echo "Extracting ${TARGET_TICKER} transcripts..."
    LOWERCASE_TARGET_TICKER=$(echo "$TARGET_TICKER" | tr '[:upper:]' '[:lower:]')
    RAW_TICKER_DIR="data/raw_${LOWERCASE_TARGET_TICKER}"

    if [ ! -d "$RAW_TICKER_DIR" ] || [ -z "$(ls -A "$RAW_TICKER_DIR" 2>/dev/null)" ]; then
        python3 scripts/extract_ticker.py "$TARGET_TICKER"
    else
        echo "✅ ${TARGET_TICKER} transcripts already extracted to ${RAW_TICKER_DIR}/. Skipping extraction."
    fi

    export MAX_WORKERS # Export for phase2_runner.py to use
    echo "Processing transcripts with LLM (this may take a while with MAX_WORKERS=$MAX_WORKERS)..."
    python3 llm_processor/phase2_runner.py "$TARGET_TICKER"

    echo "Cleaning LLM outputs and persisting to cleaned DB table..."
    python3 scripts/clean_outputs.py # Ensure this script now writes to DB directly
fi
echo "Data processing check complete."

export FASTAPI_URL="http://${FASTAPI_HOST}:${FASTAPI_PORT}"

echo "🟢 Launching FastAPI on http://${FASTAPI_HOST}:${FASTAPI_PORT}..."
exec uvicorn api.fastapi_server:app --host "$FASTAPI_HOST" --port "$FASTAPI_PORT" --reload