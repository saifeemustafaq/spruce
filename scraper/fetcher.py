import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import date

from .config import API_URL


class APIError(Exception):
    """Raised when the Prometheus API is unreachable, returns an error, or gives unexpected data."""

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


def fetch_units(retries=3, backoff_factor=2) -> list:
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

    last_exc = None
    for attempt in range(retries):
        try:
            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                    raw = resp.read()
            except urllib.error.URLError as exc:
                # urllib wraps ssl errors in URLError; unwrap to check the real cause.
                if not getattr(exc, 'reason', None) or not isinstance(exc.reason, ssl.SSLError):
                    raise exc # Let the outer block handle HTTPError or network URLError
                
                # Prometheus's cert chain has a non-critical Basic Constraints extension
                # that Python's strict SSL validation rejects on some platforms (e.g. macOS
                # Homebrew Python 3.14). GitHub Actions Ubuntu/Python 3.11 is unaffected.
                print(f"Warning: SSL verification failed ({exc.reason}); retrying without cert check.")
                unverified = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=30, context=unverified) as resp:
                    raw = resp.read()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise APIError(
                    f"Prometheus API returned non-JSON content (possible endpoint change).\n"
                    f"URL: {url}\n"
                    f"Response preview: {raw[:500]!r}"
                ) from exc

            if not isinstance(data, list):
                raise APIError(
                    f"Prometheus API response is not a list (schema may have changed).\n"
                    f"URL: {url}\n"
                    f"Type received: {type(data).__name__}\n"
                    f"Response preview: {str(data)[:500]}"
                )

            return data

        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (500, 502, 503, 504):
                wait_time = backoff_factor ** attempt
                print(f"Server returned {exc.code} {exc.reason}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                raise APIError(
                    f"Prometheus API returned HTTP {exc.code} {exc.reason}.\n"
                    f"URL: {url}\n"
                    f"This may mean the endpoint has moved or authentication is now required."
                ) from exc
        except urllib.error.URLError as exc:
            last_exc = exc
            wait_time = backoff_factor ** attempt
            print(f"Network error ({exc}). Retrying in {wait_time}s...")
            time.sleep(wait_time)
            continue

    # If we exhausted retries
    raise APIError(
        f"Network error contacting Prometheus API after {retries} attempts.\n"
        f"URL: {url}\n"
        f"Error: {last_exc}"
    ) from last_exc
