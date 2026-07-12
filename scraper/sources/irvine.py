import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime

from ..fetcher import APIError
from .base import Source, annotate_flags

# Irvine Company uses Algolia hosted search rather than a REST API.
# See docs/irvine-north-park-api.md. The search-only key is public (embedded in
# the community page HTML); if it starts returning 403/invalid-key, re-scrape it
# from the page's `page-properties-provider` config (searchAPIKey/searchAccountId).
ALGOLIA_APP_ID = "JV59LDJGMN"
ALGOLIA_API_KEY = "daadf4691bf18ebb7d7065bd85f0c972"
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"
# Every hit in this index is inherently a BMR/affordable unit.
BMR_INDEX = "prod_ica_bmrUnitAvailability"

_HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}


def _fmt_date(value: str) -> str:
    """Convert Algolia's 'YYYYMMDD' availability string to 'Mon DD, YYYY'."""
    try:
        return datetime.strptime(str(value), "%Y%m%d").strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return str(value) if value else ""


class IrvineSource(Source):
    """Irvine Company affordable-housing availability via Algolia."""

    def fetch(self, prop: dict) -> list:
        community = prop["community_id_aem"]
        payload = {
            "requests": [
                {
                    "indexName": BMR_INDEX,
                    # NOTE: filter on communityIDAEM (not communityId) or Algolia
                    # returns nbHits:0 with no error.
                    "params": f"filters=communityIDAEM:{community}&hitsPerPage=1000",
                }
            ]
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            ALGOLIA_URL, data=body, headers=_HEADERS, method="POST"
        )

        try:
            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                    raw = resp.read()
            except urllib.error.URLError as exc:
                if not getattr(exc, "reason", None) or not isinstance(
                    exc.reason, ssl.SSLError
                ):
                    raise
                unverified = ssl._create_unverified_context()
                with urllib.request.urlopen(
                    req, timeout=30, context=unverified
                ) as resp:
                    raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise APIError(
                f"Algolia returned HTTP {exc.code} {exc.reason}. The search key "
                f"may have rotated (re-scrape from the community page)."
            ) from exc
        except urllib.error.URLError as exc:
            raise APIError(f"Network error contacting Algolia: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise APIError(
                f"Algolia returned non-JSON content.\nPreview: {raw[:500]!r}"
            ) from exc

        results = data.get("results") or []
        return results[0].get("hits", []) if results else []

    def parse(self, hits: list) -> dict:
        units: dict = {}
        for h in hits:
            unit_id = h.get("objectID")
            if not unit_id:
                continue
            bmr_type = h.get("bmrType", "") or ""
            unit_type = h.get("unitTypeName", "") or ""
            plan = (
                f"{unit_type} BMR ({bmr_type})".strip()
                if bmr_type
                else f"{unit_type} BMR".strip()
            )

            price = h.get("unitStartingPrice") or {}
            rent = price.get("price")
            term = price.get("term")
            if rent and term:
                price_str = f"${rent}/{term}mo"
            elif rent:
                price_str = f"${rent}/12mo"
            else:
                price_str = ""

            available = _fmt_date((h.get("unitEarliestAvailable") or {}).get("date"))
            sqft = h.get("unitSqFt")
            floor = h.get("unitFloor")

            units[unit_id] = {
                "plan":        plan,
                "sqft":        f"{sqft} sq. ft." if sqft else "",
                "floor":       f"Floor {floor}" if floor else "",
                "available":   available,
                "price":       price_str,
                "bedrooms":    str(h.get("floorplanBed", "") or ""),
                "bathrooms":   str(h.get("floorplanBath", "") or ""),
                "section":     h.get("propertyName"),
                "unit_number": str(h.get("unitMarketingName", "") or ""),
                "bmr_type":    bmr_type,
            }

        annotate_flags(units)
        return units
