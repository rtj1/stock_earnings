# 📊 Earnings Insight Dashboard

This project provides a pipeline to extract, process, and analyze earnings call transcripts using Large Language Models (LLMs). It features a FastAPI backend for data serving and a Streamlit dashboard for interactive visualization of summarized earnings information and extracted insights.

---

## 🚀 Features

- **Automated Data Ingestion**: Downloads S&P 500 earnings call transcripts from Hugging Face.
- **Dynamic Transcript Extraction**: Extracts transcripts for a specified ticker symbol.
- **LLM Processing**: Utilizes OpenAI's GPT models (e.g., GPT-4o) to summarize transcripts and extract structured financial insights (EPS, revenue, guidance, key risks, CEO quotes).
- **Data Persistence**: Stores all processed and cleaned LLM outputs into an SQLite database (`data/earnings_insights.db`) for efficient retrieval and querying.
- **FastAPI Backend**: Serves the processed earnings data via a RESTful API.
- **Streamlit Dashboard**: Provides an interactive web interface to explore earnings summaries and insights by company, year, and quarter.
- **Error Handling & Retries**: Includes logic for retrying OpenAI API calls to handle rate limits.

---

## 📁 Project Structure

```
.
├── api/
│   └── fastapi_server.py         # FastAPI application to serve data from the database.
├── dashboard/
│   └── streamlit_app.py          # Streamlit dashboard for data visualization.
├── data/
│   ├── raw/                      # Stores all downloaded raw transcripts.
│   ├── raw_aapl/                 # Example: stores raw transcripts for a specific ticker (e.g., AAPL).
│   └── earnings_insights.db      # SQLite database for processed and cleaned data.
├── data_ingestion/
│   └── phase1_loader.py          # Script to download raw earnings transcripts.
├── llm_processor/
│   └── phase2_runner.py          # Script to process transcripts with LLMs.
├── scripts/
│   ├── clean_outputs.py          # Script to clean LLM outputs (now inserts into DB).
│   ├── extract_ticker.py         # Script to extract specific ticker transcripts from raw data.
│   └── run_all.sh                # Main script to run the entire pipeline.
├── venv/                         # Python virtual environment.
├── .env.example                  # Example environment variables file.
├── .gitignore                    # Specifies intentionally untracked files to ignore.
├── api.log                       # Log file for FastAPI.
├── README.md                     # This README file.
└── requirements.txt              # Python dependencies.
```

---

## 🛠️ Getting Started

### Prerequisites

- Python 3.8+
- Git
- An OpenAI API Key (set as `OPENAI_API_KEY` in your `.env` file)

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd earnings_insight
```

### 2. Set Up the Python Environment

The `run_all.sh` script will automatically create and activate a virtual environment and install dependencies.

### 3. Configure OpenAI API Key

Create a `.env` file in the project root based on `.env.example`:

```
OPENAI_API_KEY="your_openai_api_key_here"
```

Replace the value with your actual OpenAI API key.

---

## ▶️ Running the Pipeline

Execute the main shell script to run the entire data processing pipeline, launch the FastAPI server, and open the Streamlit dashboard:

```bash
./scripts/run_all.sh
```

**Note on `TARGET_TICKER`**: By default, the `run_all.sh` script processes `AAPL` transcripts. You can change the `TARGET_TICKER` variable in `scripts/run_all.sh` to process a different company.

**Note on `MAX_WORKERS`**: If you encounter `429 Too Many Requests` errors from OpenAI, reduce the `MAX_WORKERS` variable to a lower value (e.g., `1`) to limit the concurrency of API calls.

---

## 📊 Using the Dashboard

Once the `run_all.sh` script completes and the Streamlit dashboard opens:

- **Select Company, Year, and Quarter** from the dropdowns.
- **View Summary** of the selected earnings call.
- **Explore Extracted Insights** in a structured table format.

---

## 📡 API Endpoints

FastAPI runs on `http://127.0.0.1:8000` and provides:

- `/summary/{ticker}` – Get summary for a specific ticker.
- `/insights/{ticker}` – Get extracted insights for a specific ticker.
- `/company/{ticker}` – Get full record for a specific ticker.
- `/docs` – OpenAPI (Swagger) documentation.

> *Note: Extend endpoints with quarter/year filters as needed.*

---

## 🧹 Cleanup

To stop services, press `Ctrl+C` in the terminal where `run_all.sh` is running.

To remove generated files:

```bash
rm -rf data/raw data/raw_* data/earnings_insights.db api.log
```

---

## 🤝 Contributing

Feel free to fork the repository, open issues, or submit pull requests.

---

## 🛡 License

This project is open-source and available under the MIT License.
