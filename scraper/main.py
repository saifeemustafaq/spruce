import sys

from .config import (
    GROUPS,
    state_file, history_file,
    load_notification_config, property_controls,
)
from .fetcher import APIError
from .sources.registry import get_source
from .tracker import update_history
from . import store_mongo
from .notifier import (
    send_bmr_alert, send_api_error_alert,
    send_api_empty_alert, send_history_update_alert, send_store_error_alert,
    history_url,
)


def run_property(group: dict, prop: dict, controls: dict) -> bool:
    """Runs the full check pipeline for a single property within a group.

    ``controls`` carries the per-property {monitor, email} flags. Files and the
    MongoDB mirror are always written (so the website stays current); the
    ``email`` flag only gates outbound email for this property.

    Returns True on success, False if the property's run failed (so the overall
    process can exit non-zero while still processing other properties).
    """
    name       = prop["name"]
    key        = prop["key"]
    page_url   = prop.get("page_url", "")
    group_key  = group["key"]
    email_on   = controls["email"]
    source     = get_source(group["adapter"])

    prop_state_file = state_file(group_key, key)
    prop_history    = history_file(group_key, key)

    print(f"\n=== {group['name']} / {name} ===")
    if not email_on:
        print("  (email notifications disabled for this property)")
    print("Fetching units ...")

    try:
        raw = source.fetch(prop)
    except APIError as exc:
        print(f"ERROR: fetch failure — {exc}")
        if email_on:
            send_api_error_alert(exc, name, page_url)
        return False
    except Exception as exc:  # noqa: BLE001 - surface any adapter error as an alert
        print(f"ERROR: unexpected fetch failure — {exc}")
        if email_on:
            send_api_error_alert(exc, name, page_url)
        return False

    print(f"Source returned {len(raw)} raw record(s)")

    if len(raw) == 0:
        print("WARNING: source returned 0 records.")
        if email_on:
            send_api_empty_alert(page_url, name, page_url)
        return True

    current_units = source.parse(raw)

    plans_found = sorted(set(u["plan"] for u in current_units.values()))
    print(f"Parsed {len(current_units)} units across plans: {plans_found}")
    for uid, data in sorted(current_units.items()):
        print(f"  {uid}: {data['plan']} | {data.get('floor','')} | "
              f"{data.get('available','')} | {data.get('price','')}")

    summaries, events = update_history(prop_state_file, prop_history, current_units)

    # BMR/deal alert fires first so it lands at the top of the inbox.
    deals = [(uid, d) for uid, d in current_units.items() if d.get("is_deal")]
    if deals:
        for uid, d in deals:
            print(f"  DEAL: {uid} — {d.get('plan','')} — {d.get('price','')}")
        if email_on:
            send_bmr_alert(deals, name, page_url)
    else:
        print("No BMR / Income Limit / deal units found.")

    # Tracker alert: units added / removed / price changed / date changed.
    if summaries:
        print(f"{len(summaries)} history change(s) recorded.")
        if email_on:
            send_history_update_alert(summaries, name, page_url,
                                      history_url(group_key, key))

    # MongoDB mirror — best-effort, never blocks the (already-written) files.
    result = store_mongo.sync_property(group, prop, current_units, events)
    if result is None:
        print("  Mongo mirror: OK")
    elif result.startswith("skip:"):
        print(f"  Mongo mirror: {result}")
    else:
        print(f"  Mongo mirror FAILED: {result}")
        if email_on:
            send_store_error_alert(result, group["name"], name)

    return True


def main():
    total = sum(len(g["properties"]) for g in GROUPS)
    print(f"Tracking {len(GROUPS)} group(s), {total} propert"
          f"{'y' if total == 1 else 'ies'}")

    notif = load_notification_config()

    all_ok = True
    for group in GROUPS:
        for prop in group["properties"]:
            controls = property_controls(notif, group["key"], prop["key"])
            if not controls["monitor"]:
                print(f"\n=== {group['name']} / {prop['name']} ===")
                print("  Monitoring disabled — skipping "
                      "(no scraping, file/MongoDB writes, or emails).")
                continue
            try:
                ok = run_property(group, prop, controls)
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR: unexpected failure processing "
                      f"{group['key']}/{prop['key']} — {exc}")
                ok = False
            all_ok = all_ok and ok

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
