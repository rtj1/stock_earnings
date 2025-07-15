#!/bin/bash

# Get the directory where the script is located (e.g., /path/to/project/scripts)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Navigate to the project root (one level up from 'scripts')
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT" || { echo "❌ Error: Could not navigate to project root."; exit 1; }

echo "🚀 Starting Earnings Insight Pipeline..."

# Step 1: Create and Activate venv, then install dependencies
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to create virtual environment."
        exit 1
    fi
fi

source venv/bin/activate
echo "✅ Virtual environment activated."

echo "Installing/updating Python dependencies from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install Python dependencies. Please check requirements.txt and your internet connection."
    deactivate # Deactivate venv before exiting
    exit 1
fi
echo "✅ Dependencies installed."

# --- Define the target ticker for processing ---
# You can change this to any ticker for which you have raw data
TARGET_TICKER="AAPL"
echo "Targeting ticker: $TARGET_TICKER for processing."

# --- Database Configuration ---
DB_PATH="data/earnings_insights.db"
CLEANED_TABLE_NAME="earnings_cleaned_llm"

# --- Conditional Data Processing Steps ---
# Check if the cleaned data table in the database has any records
DB_EXISTS=false
if [ -f "$DB_PATH" ]; then
    # Use 'sqlite3 -batch' for non-interactive mode
    RECORD_COUNT=$(sqlite3 -batch "$DB_PATH" "SELECT COUNT(*) FROM $CLEANED_TABLE_NAME;" 2>/dev/null)
    if [ "$RECORD_COUNT" -gt 0 ]; then
        DB_EXISTS=true
    fi
fi

if [ "$DB_EXISTS" = true ]; then
    echo "✅ Cleaned LLM outputs in database already exist. Skipping data loading and processing."
else
    echo "⬇️ Cleaned LLM outputs in database not found or or empty. Running full data pipeline."

    echo "Downloading and preparing raw data..."
    if [ ! -d "data/raw" ] || [ -z "$(ls -A data/raw)" ]; then
        python3 data_ingestion/phase1_loader.py
        if [ $? -ne 0 ]; then echo "❌ data_ingestion/phase1_loader.py failed."; deactivate; exit 1; fi
    else
        echo "✅ Raw data already exists in data/raw/. Skipping download."
    fi

    echo "Extracting ${TARGET_TICKER} transcripts..."
    # FIX: Use tr for robust lowercase conversion
    LOWERCASE_TARGET_TICKER=$(echo "$TARGET_TICKER" | tr '[:upper:]' '[:lower:]')
    RAW_TICKER_DIR="data/raw_${LOWERCASE_TARGET_TICKER}"

    if [ ! -d "$RAW_TICKER_DIR" ] || [ -z "$(ls -A "$RAW_TICKER_DIR")" ]; then
        python3 scripts/extract_ticker.py "$TARGET_TICKER" # Pass ticker as argument
        if [ $? -ne 0 ]; then echo "❌ scripts/extract_ticker.py failed."; deactivate; exit 1; fi
    else
        echo "✅ ${TARGET_TICKER} transcripts already extracted to ${RAW_TICKER_DIR}/. Skipping extraction."
    fi

    export MAX_WORKERS=1
    echo "Processing transcripts with LLM (this may take a while with MAX_WORKERS=$MAX_WORKERS)..."
    python3 llm_processor/phase2_runner.py "$TARGET_TICKER" # Pass ticker to runner
    if [ $? -ne 0 ]; then
        echo "❌ llm_processor/phase2_runner.py failed. Check api.log for details."
    fi

    echo "Cleaning LLM outputs and persisting to cleaned DB table..."
    python3 scripts/clean_outputs.py
    if [ $? -ne 0 ]; then echo "❌ scripts/clean_outputs.py failed."; deactivate; exit 1; fi

fi
echo "Data processing check complete."
# --- End Conditional Data Processing Steps ---


# Set FastAPI URL for Streamlit
export FASTAPI_URL="http://127.0.0.1:8000"

echo "🟢 Launching FastAPI on http://127.0.0.1:8000 ..."
# Corrected FastAPI app path in run_all.sh as per typical structure
nohup uvicorn api.fastapi_server:app --reload > api.log 2>&1 &
API_PID=$!
echo "FastAPI process started with PID: $API_PID. Check api.log for details."
sleep 5 # Give FastAPI time to start and load data from DB

echo "📊 Opening Streamlit Dashboard..."
streamlit run dashboard/streamlit_app.py

echo "Shutting down FastAPI service (PID: $API_PID)..."
kill $API_PID 2>/dev/null
echo "FastAPI service stopped."

deactivate
echo "Virtual environment deactivated."

echo "Pipeline finished."