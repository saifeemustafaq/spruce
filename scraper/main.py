import json
import sys

from .config import (
    TRACKING_MODE, GROUPS,
    state_file, history_file, snapshot_path,
)
from .fetcher import APIError
from .sources.registry import get_source
from .tracker import load_snapshot, save_snapshot, compute_diff, update_history
from . import store_mongo
from .notifier import (
    send_bmr_alert, send_change_alert, send_api_error_alert,
    send_api_empty_alert, send_history_update_alert, send_store_error_alert,
    history_url,
)


def run_property(group: dict, prop: dict) -> bool:
    """Runs the full check pipeline for a single property within a group.

    Returns True on success, False if the property's run failed (so the overall
    process can exit non-zero while still processing other properties).
    """
    name       = prop["name"]
    key        = prop["key"]
    page_url   = prop.get("page_url", "")
    group_key  = group["key"]
    source     = get_source(group["adapter"])

    prop_state_file = state_file(group_key, key)
    prop_history    = history_file(group_key, key)
    prop_snapshot   = snapshot_path(group_key, key)

    print(f"\n=== {group['name']} / {name} ===")
    print("Fetching units ...")

    try:
        raw = source.fetch(prop)
    except APIError as exc:
        print(f"ERROR: fetch failure — {exc}")
        send_api_error_alert(exc, name, page_url)
        return False
    except Exception as exc:  # noqa: BLE001 - surface any adapter error as an alert
        print(f"ERROR: unexpected fetch failure — {exc}")
        send_api_error_alert(exc, name, page_url)
        return False

    print(f"Source returned {len(raw)} raw record(s)")

    if len(raw) == 0:
        print("WARNING: source returned 0 records — sending alert email.")
        send_api_empty_alert(page_url, name, page_url)
        return True

    current_units = source.parse(raw)

    plans_found = sorted(set(u["plan"] for u in current_units.values()))
    print(f"Parsed {len(current_units)} units across plans: {plans_found}")
    for uid, data in sorted(current_units.items()):
        print(f"  {uid}: {data['plan']} | {data.get('floor','')} | "
              f"{data.get('available','')} | {data.get('price','')}")

    summaries, events = update_history(prop_state_file, prop_history, current_units)

    # BMR/deal alert fires first so it lands at the top of the inbox
    if TRACKING_MODE == "bmr":
        deals = [(uid, d) for uid, d in current_units.items() if d.get("is_deal")]
        if deals:
            for uid, d in deals:
                print(f"  DEAL: {uid} — {d.get('plan','')} — {d.get('price','')}")
            send_bmr_alert(deals, name, page_url)
        else:
            print("No BMR / Income Limit / deal units found. No alert sent.")

    if summaries:
        print(f"{len(summaries)} history change(s) recorded — sending update email.")
        send_history_update_alert(summaries, name, page_url,
                                  history_url(group_key, key))

    if TRACKING_MODE == "changes":
        raw_json = json.dumps(raw, sort_keys=True, default=str)
        old_snapshot = load_snapshot(prop_snapshot)
        save_snapshot(prop_snapshot, raw_json)

        if old_snapshot is None:
            print("No previous snapshot — saving baseline.")
            send_change_alert([], [], is_first_run=True,
                              property_name=name, page_url=page_url)
        else:
            added, removed = compute_diff(old_snapshot, raw_json)
            if added or removed or summaries:
                print(f"Changes detected (+{len(added)} / -{len(removed)} lines).")
                send_change_alert(added, removed, is_first_run=False,
                                  property_name=name, page_url=page_url,
                                  changes_log=summaries)
            else:
                print("No changes detected since last run.")

    # MongoDB mirror — best-effort, never blocks the (already-written) files.
    result = store_mongo.sync_property(group, prop, current_units, events)
    if result is None:
        print("  Mongo mirror: OK")
    elif result.startswith("skip:"):
        print(f"  Mongo mirror: {result}")
    else:
        print(f"  Mongo mirror FAILED: {result}")
        send_store_error_alert(result, group["name"], name)

    return True


def main():
    total = sum(len(g["properties"]) for g in GROUPS)
    print(f"Mode: {TRACKING_MODE}")
    print(f"Tracking {len(GROUPS)} group(s), {total} propert"
          f"{'y' if total == 1 else 'ies'}")

    all_ok = True
    for group in GROUPS:
        for prop in group["properties"]:
            try:
                ok = run_property(group, prop)
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR: unexpected failure processing "
                      f"{group['key']}/{prop['key']} — {exc}")
                ok = False
            all_ok = all_ok and ok

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
