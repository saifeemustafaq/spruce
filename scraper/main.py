from .config import (
    TRACKING_MODE, TARGET_URL, SNAPSHOT_PATH, STATE_FILE, HISTORY_FILE
)
from .fetcher import scrape_page
from .parser import normalize, find_bmr_plans, parse_listings, classify
from .tracker import load_snapshot, save_snapshot, compute_diff, update_history
from .notifier import send_bmr_alert, send_change_alert

def main():
    print(f"Mode: {TRACKING_MODE}")
    print(f"Checking {TARGET_URL} ...")
    raw = scrape_page(TARGET_URL)
    text = normalize(raw)

    # Always parse units to update our local markdown history
    current_units = parse_listings(text)

    # Log what was found so GitHub Actions output is inspectable
    print(f"Parsed {len(current_units)} units across plans: "
          f"{sorted(set(u['plan'] for u in current_units.values()))}")
    for uid, data in sorted(current_units.items()):
        print(f"  {uid}: {data['plan']} | {data['floor']} | {data['available']} | {data['price']}")

    history_changes = update_history(STATE_FILE, HISTORY_FILE, current_units)

    if TRACKING_MODE == "changes":
        old = load_snapshot(SNAPSHOT_PATH)
        save_snapshot(SNAPSHOT_PATH, text)

        if old is None:
            print("No previous snapshot found — saving baseline and emailing confirmation.")
            send_change_alert([], [], is_first_run=True)
        else:
            added, removed = compute_diff(old, text)
            if added or removed or history_changes:
                print(f"Page changed: +{len(added)} lines / -{len(removed)} lines — sending email.")
                # Pass the history changes to the email so it looks nice
                send_change_alert(added, removed, is_first_run=False, changes_log=history_changes)
            else:
                print("No changes detected since last run.")

    else:  # bmr mode
        plans = find_bmr_plans(text)
        if plans:
            for p in plans:
                print(f"  FOUND [{classify(p)}]: {p['name']}")
            send_bmr_alert(plans)
        else:
            print("No BMR or Income Limit listings found. No alert sent.")


if __name__ == "__main__":
    main()
