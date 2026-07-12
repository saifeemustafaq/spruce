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


def annotate_flags(units: dict) -> dict:
    """Add is_bmr / is_income_limited / is_deal to every normalized unit.

    A unit is a "deal" when the plan mentions BMR or Income Limit, or the rent
    is under $3,000. Irvine BMR units carry "BMR" in the plan text, so they are
    always flagged.
    """
    for u in units.values():
        plan = u.get("plan", "") or ""
        rent = parse_rent(u.get("price", ""))
        is_bmr = "BMR" in plan
        is_income = "Income Limit" in plan
        u["is_bmr"] = is_bmr
        u["is_income_limited"] = is_income
        u["is_deal"] = is_bmr or is_income or (rent is not None and rent < 3000)
    return units
