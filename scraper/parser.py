from datetime import datetime


def _fmt_available(date_str: str) -> str:
    """Convert API date strings like '5/20/2026' to 'May 20, 2026'."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%b %d, %Y")
        except (ValueError, TypeError):
            pass
    return date_str  # leave unchanged if format is unrecognised


def parse_listings(units: list) -> dict:
    """
    Converts the raw API unit list into a keyed dict for the tracker.
    Key format: "G-302" (buildingNumber-unitNumber).
    """
    result = {}
    for u in units:
        key = f"{u['buildingNumber']}-{u['unitNumber']}"
        result[key] = {
            "plan":      u["floorPlanName"],
            "sqft":      f"{u['area']} sq. ft.",
            "floor":     f"Floor {u['floor']}",
            "available": _fmt_available(u["madeReadyDate"]),
            "price":     f"${u['bestRent']}/{u['bestTerm']}mo",
            "bedrooms":  u["bedrooms"],
            "bathrooms": u["bathrooms"],
        }
    return result


def find_bmr_plans(units: list) -> list:
    """
    Scans the API unit list for BMR, Income Limit floor plans, or units priced <= $3,000.
    Returns a list of matching unit dicts in the format expected by notifier.py.
    """
    found = []
    for u in units:
        name = u.get("floorPlanName", "")
        has_bmr = "BMR" in name
        has_income = "Income Limit" in name
        
        try:
            price_str = u.get("bestRent") or u.get("rent") or "999999"
            price = float(price_str)
            is_cheap = price <= 3000
        except (ValueError, TypeError):
            is_cheap = False

        if has_bmr or has_income or is_cheap:
            found.append({
                "name":       name,
                "details":    str(u),
                "has_bmr":    has_bmr,
                "has_income": has_income,
                "is_cheap":   is_cheap,
                "price":      u.get("bestRent") or u.get("rent"),
            })
    return found


def classify(plan: dict) -> str:
    labels = []
    if plan.get("has_bmr"):
        labels.append("BMR")
    if plan.get("has_income"):
        labels.append("Income Limit")
    if plan.get("is_cheap"):
        labels.append(f"Under $3k (${plan.get('price')})")
    
    return " + ".join(labels) if labels else "Deal"
