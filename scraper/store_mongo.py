"""Best-effort MongoDB mirror of the authoritative JSON/Markdown files.

The files remain the source of truth for change detection; this module simply
reflects the latest state + this run's events into MongoDB so the bmr dashboard
has a queryable copy. Every failure path (no MONGODB_URI, pymongo missing, or
any runtime/network error) is non-fatal: ``sync_property`` returns a string and
the caller keeps going, so Mongo downtime never blocks a file write.

Document shapes intentionally match bmr/scripts/seed.ts so the seed script stays
a valid "rebuild from files" recovery tool.
"""
import re
from datetime import datetime, timezone

from .config import MONGODB_URI, MONGODB_DB
from .sources.base import classify_unit, resolve_bedrooms

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


# ---------------------------------------------------------------------------
# normalization helpers (mirror seed.ts)
# ---------------------------------------------------------------------------

def _int10(s, fallback: int = 0) -> int:
    if s is None:
        return fallback
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else fallback


def _parse_price(price):
    """'$3,517/12mo' -> (3517, 12); '$3517' -> (3517, 0)."""
    if not price:
        return 0, 0
    m = re.search(r"\$([\d,]+)\s*/\s*(\d+)\s*mo", price, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(",", "")), int(m.group(2))
    only = re.search(r"\$([\d,]+)", price)
    return (int(only.group(1).replace(",", "")) if only else 0), 0


def _parse_nice_date(label):
    """'Jul 01, 2026' -> aware UTC datetime at midnight, else None."""
    if not label:
        return None
    m = re.search(r"([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})", label.strip())
    if not m:
        return None
    month = _MONTHS.get(m.group(1))
    if not month:
        return None
    return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)


def _parse_detected_at(label):
    """'Jun 25, 2026 22:30 PT' -> aware UTC datetime (PT summer = UTC-7)."""
    if not label:
        return None
    m = re.search(
        r"([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})\s+(\d{1,2}):(\d{2})", label.strip()
    )
    if not m:
        return _parse_nice_date(label)
    month = _MONTHS.get(m.group(1))
    if not month:
        return None
    # Convert PT wall time to UTC by adding 7h (PDT). Overflow past midnight is
    # handled by building the timestamp from a unix epoch offset.
    from datetime import timedelta

    base = datetime(
        int(m.group(3)), month, int(m.group(2)),
        int(m.group(4)), int(m.group(5)), tzinfo=timezone.utc,
    )
    return base + timedelta(hours=7)


def _split_unit(unit_id: str, data: dict):
    """Return (buildingNumber, unitNumber).

    Irvine units carry an explicit unit_number and have opaque objectID keys, so
    there is no building component. Prometheus keys are 'building-unit'.
    """
    if data.get("unit_number") is not None:
        return "", str(data.get("unit_number") or "")
    if "-" in unit_id:
        building, _, rest = unit_id.partition("-")
        return building, rest
    return "", unit_id


def _flags(data: dict, plan: str, rent):
    """Prefer the flags already computed by annotate_flags; recompute with the
    shared canonical logic only when they are absent (e.g. an older snapshot)."""
    if "is_deal" in data:
        return (
            bool(data.get("is_bmr")),
            bool(data.get("is_income_limited")),
            bool(data.get("is_deal")),
        )
    return classify_unit(plan, rent, data.get("bedrooms"))


def _build_unit_doc(group: dict, prop: dict, unit_id: str, data: dict, now):
    plan = data.get("plan", "")
    rent, term = _parse_price(data.get("price"))
    is_bmr, is_income, is_deal = _flags(data, plan, rent)
    building, unit_number = _split_unit(unit_id, data)
    bedrooms = resolve_bedrooms(data.get("bedrooms"), plan) or 0
    bathrooms = _int10(data.get("bathrooms"), bedrooms or 1)
    return {
        "group": group["name"],
        "groupKey": group["key"],
        "propertyKey": prop["key"],
        "unitId": unit_id,
        "buildingNumber": building,
        "unitNumber": unit_number,
        "planName": data.get("plan", ""),
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "areaSqFt": _int10(data.get("sqft")),
        "floor": _int10(data.get("floor")),
        "rent": rent,
        "leaseTermMonths": term,
        "priceLabel": data.get("price", ""),
        "availableDate": _parse_nice_date(data.get("available")),
        "availableLabel": data.get("available", ""),
        "section": data.get("section"),
        "bmrType": data.get("bmr_type"),
        "isBmr": is_bmr,
        "isIncomeLimited": is_income,
        "isDeal": is_deal,
    }


def _build_event_doc(group: dict, prop: dict, event: dict, now):
    snap = event.get("snapshot", {}) or {}
    plan = event.get("plan", "") or snap.get("plan", "")
    rent, term = _parse_price(snap.get("price"))
    is_bmr, _is_income, is_deal = _flags(snap, plan, rent)
    bedrooms = resolve_bedrooms(snap.get("bedrooms"), plan) or 0
    bathrooms = _int10(snap.get("bathrooms"), bedrooms or 1)
    return {
        "group": group["name"],
        "groupKey": group["key"],
        "propertyKey": prop["key"],
        "unitId": event.get("unit_id"),
        "eventType": event.get("event_type"),
        "planName": plan,
        "detectedAt": _parse_detected_at(event.get("detected_at")) or now,
        "changes": event.get("changes", {}),
        "section": snap.get("section"),
        "bmrType": snap.get("bmr_type"),
        "snapshot": {
            "planName": plan,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "areaSqFt": _int10(snap.get("sqft")),
            "floor": _int10(snap.get("floor")),
            "rent": rent,
            "leaseTermMonths": term,
            "priceLabel": snap.get("price", ""),
            "availableDate": _parse_nice_date(snap.get("available")),
            "availableLabel": snap.get("available", ""),
            "section": snap.get("section"),
            "bmrType": snap.get("bmr_type"),
            "isDeal": is_deal,
            "isBmr": is_bmr,
        },
        "summary": event.get("summary", ""),
    }


def _ensure_indexes(db) -> None:
    try:
        db.properties.create_index([("key", 1)], unique=True)
        db.units.create_index(
            [("groupKey", 1), ("propertyKey", 1), ("unitId", 1)], unique=True
        )
        db.units.create_index([("groupKey", 1), ("propertyKey", 1), ("status", 1)])
        db.units.create_index([("groupKey", 1), ("rent", 1)])
        db.units.create_index([("groupKey", 1), ("availableDate", 1)])
        db.events.create_index([("groupKey", 1), ("detectedAt", -1)])
        db.events.create_index([("detectedAt", -1)])
        db.events.create_index([("eventType", 1), ("detectedAt", -1)])
    except Exception:
        # Index creation is best-effort; conflicts with legacy indexes must not
        # abort a sync.
        pass


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------

def sync_property(group: dict, prop: dict, current_units: dict, events: list):
    """Mirror one property's current units + this run's events into MongoDB.

    Returns None on success, a "skip: …" string when Mongo is not configured
    (no email-worthy), or an "error: …" string on a real failure (caller emails).
    """
    if not MONGODB_URI:
        return "skip: MONGODB_URI not set"

    try:
        from pymongo import MongoClient, UpdateOne
    except ImportError:
        return "skip: pymongo not installed"

    client = None
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
        db = client[MONGODB_DB]
        now = datetime.now(timezone.utc)
        group_key = group["key"]
        prop_key = prop["key"]

        _ensure_indexes(db)

        db.properties.update_one(
            {"key": prop_key},
            {
                "$set": {
                    "key": prop_key,
                    "name": prop["name"],
                    "group": group["name"],
                    "groupKey": group_key,
                    "source": group["adapter"],
                    "propertyId": prop.get("property_id", ""),
                    "pageUrl": prop.get("page_url", ""),
                    "city": prop.get("city"),
                    "state": prop.get("state"),
                    "updatedAt": now,
                },
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )

        ops = []
        seen = []
        for unit_id, data in current_units.items():
            doc = _build_unit_doc(group, prop, unit_id, data, now)
            seen.append(unit_id)
            ops.append(
                UpdateOne(
                    {
                        "groupKey": group_key,
                        "propertyKey": prop_key,
                        "unitId": unit_id,
                    },
                    {
                        "$set": {
                            **doc,
                            "status": "active",
                            "lastSeenAt": now,
                            "updatedAt": now,
                            "removedAt": None,
                        },
                        "$setOnInsert": {"firstSeenAt": now},
                    },
                    upsert=True,
                )
            )
        if ops:
            db.units.bulk_write(ops, ordered=False)

        # Flip units no longer present to removed (idempotent).
        db.units.update_many(
            {
                "groupKey": group_key,
                "propertyKey": prop_key,
                "unitId": {"$nin": seen},
                "status": {"$ne": "removed"},
            },
            {"$set": {"status": "removed", "removedAt": now, "updatedAt": now}},
        )

        if events:
            db.events.insert_many(
                [_build_event_doc(group, prop, e, now) for e in events],
                ordered=False,
            )

        return None
    except Exception as exc:  # noqa: BLE001 - best-effort mirror
        return f"error: {type(exc).__name__}: {exc}"
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
