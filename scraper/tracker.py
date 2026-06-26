import os
import json
from datetime import datetime

def load_snapshot(snapshot_path):
    if os.path.exists(snapshot_path):
        with open(snapshot_path) as f:
            return f.read()
    return None

def save_snapshot(snapshot_path, text):
    with open(snapshot_path, "w") as f:
        f.write(text)

def compute_diff(old_text, new_text):
    old_lines = old_text.splitlines() if old_text else []
    new_lines = new_text.splitlines()
    old_set = set(old_lines)
    new_set = set(new_lines)
    added   = [l for l in new_lines if l not in old_set]
    removed = [l for l in old_lines if l not in new_set]
    return added, removed

def update_history(state_file, history_file, current_units):
    """
    Compares current units against saved state, records changes to Markdown, 
    and saves the new state. Returns a list of detected changes.
    """
    old_state = {}
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            try:
                old_state = json.load(f)
            except json.JSONDecodeError:
                pass
            
    # Initialize Markdown file if it doesn't exist
    if not os.path.exists(history_file):
        # Create directory if needed
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        with open(history_file, "w") as f:
            f.write("# Apartment Listings History\n\n")
            f.write("| Date | Unit | Plan | Event | Details |\n")
            f.write("|---|---|---|---|---|\n")

    today = datetime.now().strftime('%Y-%m-%d %H:%M')
    changes_detected = []

    # Check for New Units or Price Changes
    for unit_id, data in current_units.items():
        if unit_id not in old_state:
            changes_detected.append(
                f"| {today} | {unit_id} | {data['plan']} | 🟢 Added | Price: {data['price']} |"
            )
        elif old_state[unit_id]["price"] != data["price"]:
            changes_detected.append(
                f"| {today} | {unit_id} | {data['plan']} | 🟡 Price Changed | {old_state[unit_id]['price']} ➔ {data['price']} |"
            )

    # Check for Removed Units
    for unit_id, data in old_state.items():
        if unit_id not in current_units:
            changes_detected.append(
                f"| {today} | {unit_id} | {data['plan']} | 🔴 Removed | Was {data['price']} |"
            )

    # Append changes to Markdown
    if changes_detected:
        with open(history_file, "a") as f:
            f.write("\n".join(changes_detected) + "\n")
            
    # Save new state
    with open(state_file, "w") as f:
        json.dump(current_units, f, indent=2)
        
    return changes_detected
