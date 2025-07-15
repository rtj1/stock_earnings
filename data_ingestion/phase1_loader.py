from datasets import load_dataset
import os
import json
import logging # Import logging

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

os.makedirs("data/raw", exist_ok=True)

def run():
    logger.info("🔁 Loading dataset from Hugging Face (kurry/sp500_earnings_transcripts)...")
    try:
        dataset = load_dataset("kurry/sp500_earnings_transcripts", split="train")
        count = 0

        for record in dataset:
            cleaned = {
                "company": record["company_name"],
                "ticker": record["symbol"],
                "quarter": f"Q{record['quarter']}_{record['year']}",
                "date": record["date"],
                "transcript": record["content"]
            }

            # Save raw file
            fname = f"{cleaned['ticker']}_{cleaned['quarter']}.json"
            fpath = os.path.join("data/raw", fname)
            with open(fpath, "w") as f:
                json.dump(cleaned, f, indent=2)
            count += 1

            if count % 100 == 0:
                logger.info(f"Saved {count} transcripts to {fpath}...")

        logger.info(f"✅ Loaded and saved {count} transcripts to data/raw/")
    except Exception as e:
        logger.critical(f"❌ Critical error during dataset loading or saving: {e}", exc_info=True)

if __name__ == "__main__":
    run()