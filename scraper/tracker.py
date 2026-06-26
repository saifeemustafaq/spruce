import os
import json
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    _PT = ZoneInfo("America/Los_Angeles")  # Handles PST/PDT automatically
except ImportError:
    # Fallback for Python < 3.9: hardcode PDT (UTC-7). Won't auto-switch for DST.
    _PT = timezone(timedelta(hours=-7))

_TABLE_HEADER = (
    "| # | Unit | Sq.Ft. | Floor | Available | Event | Details | Date |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


# ---------------------------------------------------------------------------
# snapshot helpers (used by main.py in "changes" mode)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _norm_price(price: str) -> str:
    """Strips formatting differences (commas) so $3,581/12mo == $3581/12mo."""
    return price.replace(",", "") if price else price


# ---------------------------------------------------------------------------
# per-plan section helpers
# ---------------------------------------------------------------------------

def _read_sections(history_file: str) -> tuple[dict, list]:
    """
    Parses the history file into per-plan sections.

    Returns:
        sections: {plan_name: [data_row_strings]}
        order:    plan names in the order they first appeared
    """
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current_plan = None
    in_table = False

    if not os.path.exists(history_file):
        return sections, order

    with open(history_file, "r") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith("## "):
                current_plan = line[3:].strip()
                if current_plan not in sections:
                    sections[current_plan] = []
                    order.append(current_plan)
                in_table = False
            elif line.startswith("| #") or line.startswith("|---"):
                in_table = True
            elif in_table and current_plan and line.startswith("|"):
                sections[current_plan].append(line)

    return sections, order


def _write_sections(history_file: str, sections: dict, order: list) -> None:
    """Writes the full history file with one table per plan."""
    dir_name = os.path.dirname(history_file)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    with open(history_file, "w") as f:
        f.write("# Apartment Listings History\n\n")
        for plan in order:
            f.write(f"## {plan}\n\n")
            f.write(_TABLE_HEADER)
            for row in sections[plan]:
                f.write(row + "\n")
            f.write("\n")


def _is_blank(history_file: str) -> bool:
    """True when the history file is missing or contains no data rows."""
    if not os.path.exists(history_file):
        return True
    _, order = _read_sections(history_file)
    return len(order) == 0


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------

def update_history(state_file: str, history_file: str, current_units: dict) -> list:
    """
    Compares current units against saved state, records changes into per-plan
    tables in the Markdown history, and saves the new state.

    Each plan section has its own sequential serial numbers starting at 1.
    Within a single run, new entries are sorted by unit ID within each plan.

    Returns a list of human-readable change summary strings.
    """
    blank = _is_blank(history_file)

    if blank:
        sections: dict[str, list[str]] = {}
        order: list[str] = []
        old_state: dict = {}
    else:
        sections, order = _read_sections(history_file)
        old_state = {}
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                try:
                    old_state = json.load(f)
                except json.JSONDecodeError:
                    pass

    today = datetime.now(tz=_PT).strftime("%Y-%m-%d %H:%M PT")

    # Collect changes grouped by plan
    plan_changes: dict[str, list[dict]] = {}

    for unit_id, data in current_units.items():
        plan = data["plan"]
        if unit_id not in old_state:
            entry = {
                "unit_id": unit_id,
                "row_tpl": f"| {{n}} | {unit_id} | {data['sqft']} | {data['floor']} | {data['available']} | 🟢 Added | Price: {data['price']} | {today} |",
                "summary": f"🟢 Added {unit_id} ({plan})",
            }
        elif _norm_price(old_state[unit_id].get("price", "")) != _norm_price(data["price"]):
            entry = {
                "unit_id": unit_id,
                "row_tpl": f"| {{n}} | {unit_id} | {data['sqft']} | {data['floor']} | {data['available']} | 🟡 Price Changed | {old_state[unit_id].get('price')} ➔ {data['price']} | {today} |",
                "summary": f"🟡 Price Changed {unit_id} ({plan})",
            }
        elif old_state[unit_id].get("available") != data["available"]:
            entry = {
                "unit_id": unit_id,
                "row_tpl": f"| {{n}} | {unit_id} | {data['sqft']} | {data['floor']} | {data['available']} | 🔵 Date Changed | {old_state[unit_id].get('available')} ➔ {data['available']} | {today} |",
                "summary": f"🔵 Date Changed {unit_id} ({plan})",
            }
        else:
            continue

        plan_changes.setdefault(plan, []).append(entry)

    for unit_id, data in old_state.items():
        if unit_id not in current_units:
            plan = data["plan"]
            entry = {
                "unit_id": unit_id,
                "row_tpl": f"| {{n}} | {unit_id} | {data.get('sqft','?')} | {data.get('floor','?')} | {data.get('available','?')} | 🔴 Removed | Was {data.get('price')} | {today} |",
                "summary": f"🔴 Removed {unit_id} ({plan})",
            }
            plan_changes.setdefault(plan, []).append(entry)

    summaries: list[str] = []

    for plan in sorted(plan_changes.keys()):
        entries = sorted(plan_changes[plan], key=lambda e: e["unit_id"])

        # Ensure the plan section exists in the ordered structure
        if plan not in sections:
            sections[plan] = []
            order.append(plan)
        order_sorted = sorted(order)  # keep plans alphabetically ordered in file
        order[:] = order_sorted

        # Serial numbers continue from existing rows in this plan's table
        next_n = len(sections[plan]) + 1

        for i, entry in enumerate(entries):
            sections[plan].append(entry["row_tpl"].format(n=next_n + i))
            summaries.append(entry["summary"])

    if plan_changes:
        _write_sections(history_file, sections, order)

    with open(state_file, "w") as f:
        json.dump(current_units, f, indent=2)

    return summaries
