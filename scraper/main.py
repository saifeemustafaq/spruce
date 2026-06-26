import json
import os
import sys

from .config import (
    TRACKING_MODE, SPRUCE_PAGE_URL, SNAPSHOT_PATH, STATE_FILE, HISTORY_FILE, API_URL
)
from .fetcher import fetch_units, APIError
from .parser import parse_listings, find_bmr_plans, classify
from .tracker import load_snapshot, save_snapshot, compute_diff, update_history
from .notifier import send_bmr_alert, send_change_alert, send_api_error_alert, send_api_empty_alert, send_history_update_alert


def main():
    print(f"Mode: {TRACKING_MODE}")
    print(f"Fetching units from Prometheus API ...")

    try:
        units = fetch_units()
    except APIError as exc:
        print(f"ERROR: API failure — {exc}")
        send_api_error_alert(exc)
        sys.exit(1)

    print(f"API returned {len(units)} units")

    if len(units) == 0:
        print("WARNING: API returned 0 units — sending alert email.")
        send_api_empty_alert(API_URL)
        sys.exit(0)

    current_units = parse_listings(units)

    # Log what was found so the GitHub Actions run log is easy to inspect
    plans_found = sorted(set(u["plan"] for u in current_units.values()))
    print(f"Parsed {len(current_units)} units across plans: {plans_found}")
    for uid, data in sorted(current_units.items()):
        print(f"  {uid}: {data['plan']} | {data['floor']} | {data['available']} | {data['price']}")

    history_changes = update_history(STATE_FILE, HISTORY_FILE, current_units)

    if history_changes:
        print(f"{len(history_changes)} history change(s) recorded — sending update email.")
        send_history_update_alert(history_changes)

    if TRACKING_MODE == "changes":
        # Snapshot is now the raw JSON from the API, not scraped page text
        raw_json = json.dumps(units, sort_keys=True)
        old_snapshot = load_snapshot(SNAPSHOT_PATH)
        save_snapshot(SNAPSHOT_PATH, raw_json)

        if old_snapshot is None:
            print("No previous snapshot — saving baseline and emailing confirmation.")
            send_change_alert([], [], is_first_run=True)
        else:
            added, removed = compute_diff(old_snapshot, raw_json)
            if added or removed or history_changes:
                print(f"Changes detected (+{len(added)} / -{len(removed)} lines) — sending email.")
                send_change_alert(added, removed, is_first_run=False, changes_log=history_changes)
            else:
                print("No changes detected since last run.")

    else:  # bmr mode
        bmr_plans = find_bmr_plans(units)
        if bmr_plans:
            for p in bmr_plans:
                print(f"  FOUND [{classify(p)}]: {p['name']}")
            send_bmr_alert(bmr_plans)
        else:
            print("No BMR or Income Limit listings found. No alert sent.")


if __name__ == "__main__":
    main()
