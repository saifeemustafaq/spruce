import json
import sys

from .config import (
    TRACKING_MODE, PROPERTIES,
    api_url, state_file, history_file, snapshot_path,
)
from .fetcher import fetch_units, APIError
from .parser import parse_listings, find_bmr_plans, classify
from .tracker import load_snapshot, save_snapshot, compute_diff, update_history
from .notifier import (
    send_bmr_alert, send_change_alert, send_api_error_alert,
    send_api_empty_alert, send_history_update_alert, history_url,
)


def run_property(prop: dict) -> bool:
    """Runs the full check pipeline for a single property.

    Returns True on success, False if the property's run failed (so the
    overall process can exit non-zero while still processing other properties).
    """
    name     = prop["name"]
    key      = prop["key"]
    page_url = prop["page_url"]
    url      = api_url(prop["property_id"])

    prop_state_file = state_file(key)
    prop_history    = history_file(key)
    prop_snapshot   = snapshot_path(key)

    print(f"\n=== {name} ===")
    print(f"Fetching units from Prometheus API ...")

    try:
        units = fetch_units(url)
    except APIError as exc:
        print(f"ERROR: API failure — {exc}")
        send_api_error_alert(exc, name, page_url)
        return False

    print(f"API returned {len(units)} units")

    if len(units) == 0:
        print("WARNING: API returned 0 units — sending alert email.")
        send_api_empty_alert(url, name, page_url)
        return True

    current_units = parse_listings(units)

    # Log what was found so the GitHub Actions run log is easy to inspect
    plans_found = sorted(set(u["plan"] for u in current_units.values()))
    print(f"Parsed {len(current_units)} units across plans: {plans_found}")
    for uid, data in sorted(current_units.items()):
        print(f"  {uid}: {data['plan']} | {data['floor']} | {data['available']} | {data['price']}")

    history_changes = update_history(prop_state_file, prop_history, current_units)

    # BMR alert fires first so it lands at the top of your inbox
    if TRACKING_MODE == "bmr":
        bmr_plans = find_bmr_plans(units)
        if bmr_plans:
            for p in bmr_plans:
                print(f"  FOUND [{classify(p)}]: {p['name']}")
            send_bmr_alert(bmr_plans, name, page_url)
        else:
            print("No BMR or Income Limit listings found. No alert sent.")

    if history_changes:
        print(f"{len(history_changes)} history change(s) recorded — sending update email.")
        send_history_update_alert(history_changes, name, page_url, history_url(key))

    if TRACKING_MODE == "changes":
        # Snapshot is now the raw JSON from the API, not scraped page text
        raw_json = json.dumps(units, sort_keys=True)
        old_snapshot = load_snapshot(prop_snapshot)
        save_snapshot(prop_snapshot, raw_json)

        if old_snapshot is None:
            print("No previous snapshot — saving baseline and emailing confirmation.")
            send_change_alert([], [], is_first_run=True, property_name=name, page_url=page_url)
        else:
            added, removed = compute_diff(old_snapshot, raw_json)
            if added or removed or history_changes:
                print(f"Changes detected (+{len(added)} / -{len(removed)} lines) — sending email.")
                send_change_alert(added, removed, is_first_run=False, property_name=name,
                                  page_url=page_url, changes_log=history_changes)
            else:
                print("No changes detected since last run.")

    return True


def main():
    print(f"Mode: {TRACKING_MODE}")
    print(f"Tracking {len(PROPERTIES)} propert{'y' if len(PROPERTIES) == 1 else 'ies'}: "
          f"{', '.join(p['name'] for p in PROPERTIES)}")

    all_ok = True
    for prop in PROPERTIES:
        try:
            ok = run_property(prop)
        except Exception as exc:
            print(f"ERROR: unexpected failure processing {prop['name']} — {exc}")
            ok = False
        all_ok = all_ok and ok

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
