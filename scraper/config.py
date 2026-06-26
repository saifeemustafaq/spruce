import os

# Prometheus internal JSON API — returns all currently available units
API_URL = "https://shopping.prometheusapartments-prod-west2.com/3323021/available-units"

# Human-readable listing page — used in email alert links only
SPRUCE_PAGE_URL = "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce"

GMAIL_USER = "saifeemustafaq@gmail.com"

STATE_FILE = "scraper/listings_state.json"
HISTORY_FILE = "scraper/listings_history.md"
SNAPSHOT_PATH = "scraper/snapshot.json"

# Set as a GitHub repo variable (Settings → Variables → Actions):
#   TRACKING_MODE = bmr      → only email when BMR/Income Limit unit appears
#   TRACKING_MODE = changes  → email whenever anything on the page changes
TRACKING_MODE = os.environ.get("TRACKING_MODE", "bmr").strip().lower()

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
