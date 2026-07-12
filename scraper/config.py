import os

# Prometheus internal JSON API base. Each property has its own numeric ID;
# the per-property endpoint is API_BASE/<property_id>/available-units.
API_BASE = "https://shopping.prometheusapartments-prod-west2.com"

# Tracked apartment groups. Each group is served by an adapter (see
# scraper/sources/) and contains one or more properties. To add a property,
# append to the group's "properties"; to add a whole new group (e.g. Essex),
# add a new adapter under scraper/sources/ and a new entry here.
GROUPS = [
    {
        "key":     "prometheus",
        "name":    "Prometheus",
        "adapter": "prometheus",
        "properties": [
            {
                "key":         "spruce",
                "name":        "Spruce",
                "property_id": "3323021",
                "page_url":    "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce",
                "city":        "Sunnyvale",
                "state":       "CA",
            },
            {
                "key":         "kensington-place",
                "name":        "Kensington Place",
                "property_id": "1023662",
                "page_url":    "https://prometheusapartments.com/ca/sunnyvale-apartments/kensington-place",
                "city":        "Sunnyvale",
                "state":       "CA",
            },
        ],
    },
    {
        "key":     "irvine",
        "name":    "Irvine Company",
        "adapter": "irvine",
        "properties": [
            {
                "key":              "north-park",
                "name":             "North Park",
                "community_id_aem": "d44b004c-6b62-4d26-9381-15bcd314d16e",
                "property_id":      "1078197",
                "page_url":         "https://www.irvinecompanyapartments.com/locations/northern-california/san-jose/north-park/affordable-housing.html",
                "city":             "San Jose",
                "state":            "CA",
            },
        ],
    },
]

DATA_DIR = "scraper/data"


def api_url(property_id: str) -> str:
    return f"{API_BASE}/{property_id}/available-units"


def state_file(group_key: str, key: str) -> str:
    return f"{DATA_DIR}/{group_key}/{key}/listings_state.json"


def history_file(group_key: str, key: str) -> str:
    return f"{DATA_DIR}/{group_key}/{key}/listings_history.md"


def snapshot_path(group_key: str, key: str) -> str:
    return f"{DATA_DIR}/{group_key}/{key}/snapshot.json"


GMAIL_USER = "saifeemustafaq@gmail.com"

# Set as a GitHub repo variable (Settings → Variables → Actions):
#   TRACKING_MODE = bmr      → only email when BMR/Income Limit/deal unit appears
#   TRACKING_MODE = changes  → email whenever anything on the page changes
TRACKING_MODE = os.environ.get("TRACKING_MODE", "bmr").strip().lower()

GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# MongoDB mirror (best-effort). If unset, the scraper writes files only.
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB = os.environ.get("MONGODB_DB", "bmr")
