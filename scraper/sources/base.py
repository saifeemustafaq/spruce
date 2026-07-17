import re
from abc import ABC, abstractmethod


class Source(ABC):
    """A per-group data adapter.

    Each group (Prometheus, Irvine, …) implements a Source that knows how to
    fetch raw availability records for one of its properties and normalize them
    into the shape the tracker expects.

    ``parse`` must return a dict keyed by a unit id that is unique *within the
    property*, where each value has at least:
        plan, sqft, floor, available, price, bedrooms, bathrooms
    and may also include:
        section       — intra-property grouping label (e.g. sub-community)
        unit_number   — human unit number when the key isn't building-unit
        bmr_type      — affordability tier, when applicable
    ``annotate_flags`` fills in is_bmr / is_income_limited / is_deal.
    """

    @abstractmethod
    def fetch(self, prop: dict) -> list:
        """Return a list of raw records for a single property."""

    @abstractmethod
    def parse(self, raw_units: list) -> dict:
        """Normalize raw records into {unit_id: {…}}."""


def parse_rent(price: str):
    """Extract the integer dollar amount from a price label like '$3,517/12mo'."""
    if not price:
        return None
    m = re.search(r"\$(\d[\d,]*)", price)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_beds(value):
    """Bedroom count as an int (``0`` is a valid studio).

    Returns ``None`` when the value is missing/blank/unparseable, so callers can
    distinguish "no data" (fall back to the plan name) from a real studio ``0``.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


def plan_bedrooms(plan: str):
    """Best-effort bedroom count derived from the plan name; ``None`` if unknown.

    Handles the naming schemes we see across adapters:
      - "Studio A" / "Studio BMR (...)"      → 0
      - "2 Bedroom", "2BR", "2 Bed"           → 2   (Irvine-style)
      - "Plan 2C with Den", "Plan 1B"         → 2/1 (Prometheus-style)
    """
    if not plan:
        return None
    if "studio" in plan.lower():
        return 0
    m = re.search(r"(\d+)\s*(?:bed|bedroom|br)\b", plan, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\bPlan\s+(\d+)", plan, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def resolve_bedrooms(bedrooms_field, plan: str):
    """Resolve a bedroom count: trust the portal's numeric field, and only fall
    back to the plan name when that field is missing/unparseable. Returns
    ``None`` when neither source yields a count."""
    beds = parse_beds(bedrooms_field)
    if beds is not None:
        return beds
    return plan_bedrooms(plan)


def is_price_deal(bedrooms, rent) -> bool:
    """Bedroom-aware price threshold (``bedrooms`` is a resolved int or None):
      - 2BR+ (incl. "2B with Den" and 3BR): rent under $4,000
      - studio / 1BR:                        rent under $3,000
      - unknown bedroom count:               treated as 2BR+ (under $4,000) so a
        2BR+ is never missed when metadata is absent.
    """
    if rent is None:
        return False
    if bedrooms is None or bedrooms >= 2:
        return rent < 4000
    return rent < 3000


def classify_unit(plan: str, rent, bedrooms_field):
    """Canonical deal classification shared by the scraper, the MongoDB mirror
    and the seed script.

    Returns ``(is_bmr, is_income_limited, is_deal)`` where a unit is a deal when
    the plan mentions BMR or Income Limit, or it clears the bedroom-aware price
    threshold (see ``is_price_deal``).
    """
    plan = plan or ""
    is_bmr = "BMR" in plan
    is_income = "Income Limit" in plan
    beds = resolve_bedrooms(bedrooms_field, plan)
    is_deal = is_bmr or is_income or is_price_deal(beds, rent)
    return is_bmr, is_income, is_deal


def annotate_flags(units: dict) -> dict:
    """Add is_bmr / is_income_limited / is_deal to every normalized unit.

    A unit is a "deal" when the plan mentions BMR or Income Limit, or the rent
    clears the bedroom-aware price threshold (2BR+ under $4,000; studio/1BR
    under $3,000). The bedroom count falls back to the plan name when the
    portal's numeric field is missing. Irvine BMR units carry "BMR" in the plan
    text, so they are always flagged.
    """
    for u in units.values():
        rent = parse_rent(u.get("price", ""))
        is_bmr, is_income, is_deal = classify_unit(
            u.get("plan", ""), rent, u.get("bedrooms")
        )
        u["is_bmr"] = is_bmr
        u["is_income_limited"] = is_income
        u["is_deal"] = is_deal
    return units
