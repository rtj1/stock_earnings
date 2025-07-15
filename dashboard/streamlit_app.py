import streamlit as st
import requests
import pandas as pd
import os
import logging

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration for FastAPI Server URL ---
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

# --- Helper to parse quarter string ---
def parse_quarter(quarter_str):
    try:
        q, y = quarter_str.split("_")
        return q, int(y)
    except:
        logger.warning(f"Could not parse quarter string: {quarter_str}")
        return "QX", 0 # Fallback values

# --- Load initial data (ticker list and quarter map) from FastAPI ---
@st.cache_data
def load_ticker_quarter_map_from_api():
    """
    Loads all available tickers, years, and quarters from the FastAPI server
    to populate dropdowns.
    """
    try:
        logger.info(f"Fetching ticker/quarter map from FastAPI at {FASTAPI_URL}/tickers_quarters")
        response = requests.get(f"{FASTAPI_URL}/tickers_quarters")
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        return response.json() # Returns a dict like {ticker: {year: [q1, q2]}}
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to FastAPI server at {FASTAPI_URL}. Is it running?")
        st.error(f"Error: Could not connect to the API server at {FASTAPI_URL}. Please ensure it is running.")
        st.stop()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching ticker list: {e}")
        st.error(f"Error fetching ticker list from API: {e}")
        st.stop()
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching tickers: {e}", exc_info=True)
        st.error(f"An unexpected error occurred: {e}")
        st.stop()

# --- Helper to fetch a single record from FastAPI ---
@st.cache_data
def get_company_record_from_api(ticker: str, quarter_key: str):
    """Fetches a single company's full record for a specific quarter from the FastAPI server."""
    try:
        logger.info(f"Fetching full record for {ticker} - {quarter_key} from FastAPI.")
        response = requests.get(f"{FASTAPI_URL}/company/{ticker}/{quarter_key}")
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"No record found for {ticker} - {quarter_key} on the API (404).")
            st.warning(f"No record found for {ticker} - {quarter_key} on the API.")
            return None
        logger.error(f"HTTP error fetching data for {ticker} - {quarter_key}: {e}")
        st.error(f"Error fetching data for {ticker} - {quarter_key}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching data for {ticker} - {quarter_key}: {e}", exc_info=True)
        st.error(f"Network error fetching data for {ticker} - {quarter_key}: {e}")
        return None

# --- Streamlit UI ---
st.title("📊 Earnings Call Insight Dashboard")

# Load the ticker-quarter map from FastAPI
ticker_quarter_map = load_ticker_quarter_map_from_api()

if not ticker_quarter_map:
    st.info("No companies or quarters found in data. Please ensure FastAPI is running and data is loaded into the database.")
    st.stop()

# Prepare data for selectboxes
available_tickers = sorted(ticker_quarter_map.keys())
selected_ticker = st.selectbox("Select Company", available_tickers)

# Filter years based on selected ticker
years_for_ticker = sorted(list(ticker_quarter_map.get(selected_ticker, {}).keys()))
if not years_for_ticker:
    st.warning(f"No years found for {selected_ticker}.")
    st.stop()
selected_year = st.selectbox("Select Year", years_for_ticker)

# Filter quarters based on selected ticker and year
quarters_for_year = ticker_quarter_map.get(selected_ticker, {}).get(selected_year, [])
if not quarters_for_year:
    st.warning(f"No quarters found for {selected_ticker} in {selected_year}.")
    st.stop()
selected_quarter = st.selectbox("Select Quarter", quarters_for_year)

# Construct quarter_key for API call
quarter_key = f"{selected_quarter}_{selected_year}"

# Fetch and display data from FastAPI based on selections
with st.spinner(f"Fetching data for {selected_ticker} ({quarter_key})..."):
    record_to_display = get_company_record_from_api(selected_ticker, quarter_key)

if not record_to_display:
    st.info("Please select a company, year, and quarter to view insights.")
    st.stop()

# Summary block
st.subheader(f"🗂️ Summary for {record_to_display.get('ticker', 'N/A')} ({record_to_display.get('quarter', 'N/A')})")
st.markdown(f"""
<div style="background-color:#f8f9fa; padding:1rem; border-left:4px solid #4CAF50;">
{record_to_display.get("summary", "_No summary available._")}
</div>
""", unsafe_allow_html=True)

# Insights block
st.subheader("📌 Extracted Insights")

insights = record_to_display.get("insights", {})
if not insights:
    st.info("No insights available.")
else:
    # Ensure insights are displayed as a DataFrame properly
    if isinstance(insights, dict):
        df_insights = pd.DataFrame([insights])
    else:
        try:
            df_insights = pd.DataFrame(insights)
        except ValueError:
            st.warning("Insights format not recognized for tabular display.")
            st.json(insights)
            df_insights = pd.DataFrame()

    if not df_insights.empty:
        st.dataframe(df_insights, use_container_width=True)

# Debug or raw view
with st.expander("🛠 View Raw JSON"):
    st.json(record_to_display)