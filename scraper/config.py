import os

TARGET_URL = "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce"
GMAIL_USER = "saifeemustafaq@gmail.com"

SNAPSHOT_PATH = "scraper/snapshot.txt"
STATE_FILE = "scraper/listings_state.json"
HISTORY_FILE = "scraper/listings_history.md"

# Set as a GitHub repo variable (Settings → Variables → Actions):
#   TRACKING_MODE = bmr      → only email when BMR/Income Limit unit appears
#   TRACKING_MODE = changes  → email whenever anything on the page changes
TRACKING_MODE = os.environ.get("TRACKING_MODE", "bmr").strip().lower()

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
