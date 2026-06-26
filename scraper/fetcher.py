import json
import ssl
import urllib.error
import urllib.request
from datetime import date

from .config import API_URL

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept":   "application/json, text/plain, */*",
    "Origin":   "https://prometheusapartments.com",
    "Referer":  "https://prometheusapartments.com/",
}


def fetch_units() -> list:
    """
    Calls the Prometheus internal JSON API and returns the list of available units.
    The date parameter tells the API to return units available from today onwards.
    No third-party libraries required — uses Python stdlib only.

    The API requires browser-like headers (Origin/Referer) to avoid a 403.
    It also uses a certificate chain with a non-critical Basic Constraints extension
    that some Python builds reject; the fallback unverified context handles that.
    """
    today = date.today().strftime("%Y-%m-%d")
    url = f"{API_URL}?date={today}"
    req = urllib.request.Request(url, headers=_HEADERS)

    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as exc:
        # urllib wraps ssl errors in URLError; unwrap to check the real cause.
        if not isinstance(exc.reason, ssl.SSLError):
            raise
        # Prometheus's cert chain has a non-critical Basic Constraints extension
        # that Python's strict SSL validation rejects on some platforms (e.g. macOS
        # Homebrew Python 3.14). GitHub Actions Ubuntu/Python 3.11 is unaffected.
        print(f"Warning: SSL verification failed ({exc.reason}); retrying without cert check.")
        unverified = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=30, context=unverified) as resp:
            return json.loads(resp.read())
