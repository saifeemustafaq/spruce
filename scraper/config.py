import os

# Prometheus internal JSON API base. Each property has its own numeric ID;
# the per-property endpoint is API_BASE/<property_id>/available-units.
API_BASE = "https://shopping.prometheusapartments-prod-west2.com"

# Properties tracked by the scraper. To add a new one, find its property ID
# (the number in the available-units request on its listing page) and append
# an entry here — no other code changes required.
PROPERTIES = [
    {
        "key":         "spruce",
        "name":        "Spruce",
        "property_id": "3323021",
        "page_url":    "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce",
    },
    {
        "key":         "kensington-place",
        "name":        "Kensington Place",
        "property_id": "1023662",
        "page_url":    "https://prometheusapartments.com/ca/sunnyvale-apartments/kensington-place",
    },
]

DATA_DIR = "scraper/data"


def api_url(property_id: str) -> str:
    return f"{API_BASE}/{property_id}/available-units"


def state_file(key: str) -> str:
    return f"{DATA_DIR}/{key}/listings_state.json"


def history_file(key: str) -> str:
    return f"{DATA_DIR}/{key}/listings_history.md"


def snapshot_path(key: str) -> str:
    return f"{DATA_DIR}/{key}/snapshot.json"


GMAIL_USER = "saifeemustafaq@gmail.com"

# Set as a GitHub repo variable (Settings → Variables → Actions):
#   TRACKING_MODE = bmr      → only email when BMR/Income Limit unit appears
#   TRACKING_MODE = changes  → email whenever anything on the page changes
TRACKING_MODE = os.environ.get("TRACKING_MODE", "bmr").strip().lower()

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
