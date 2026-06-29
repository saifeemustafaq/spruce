import os
import re
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

_LATEST_UPDATES_HEADING = "Latest Updates"


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


def _is_deal(data: dict) -> bool:
    """True when the unit is BMR, Income Limit, or priced under $3,000."""
    plan = data.get("plan", "")
    if "BMR" in plan or "Income Limit" in plan:
        return True
    m = re.search(r"\$(\d[\d,]*)", data.get("price", ""))
    if m:
        try:
            return int(m.group(1).replace(",", "")) < 3000
        except ValueError:
            pass
    return False


def _hi(text: str, deal: bool) -> str:
    """Wraps text in bold monospace if this is a deal row."""
    return f"**`{text}`**" if deal else text


def _count_whole_rows(rows: list) -> int:
    """Counts rows whose serial number is a plain integer (not X.Y)."""
    count = 0
    for row in rows:
        cols = [c.strip() for c in row.split("|")]
        if len(cols) >= 2 and cols[1].isdigit():
            count += 1
    return count


# ---------------------------------------------------------------------------
# per-plan section helpers
# ---------------------------------------------------------------------------

def _read_sections(history_file: str) -> tuple:
    """
    Parses the history file into per-plan sections.

    Returns:
        sections:          {plan_name: [data_row_strings]}
        order:             plan names in the order they first appeared
        unit_base_serials: {unit_id: str} — the whole-number serial from the
                           most recent 🟢 Added row for that unit
        unit_sub_counts:   {unit_id: int} — how many sub-entries (.1, .2 …)
                           already exist under the unit's current base serial
        latest_updates:    [bullet_string, …] — existing Latest Updates lines,
                           newest first
    """
    sections: dict = {}
    order: list = []
    unit_base_serials: dict = {}
    unit_sub_counts: dict = {}
    latest_updates: list = []
    current_plan = None
    in_table = False
    in_latest = False

    if not os.path.exists(history_file):
        return sections, order, unit_base_serials, unit_sub_counts, latest_updates

    with open(history_file, "r") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith("## "):
                heading = line[3:].strip()
                if heading == _LATEST_UPDATES_HEADING:
                    # Switch into Latest Updates parsing mode
                    in_latest = True
                    in_table = False
                    current_plan = None
                    continue
                in_latest = False
                current_plan = heading
                # Strip "(N units available)" suffix written by _write_sections
                if " (" in current_plan and current_plan.endswith(")"):
                    current_plan = current_plan[: current_plan.index(" (")].strip()
                if current_plan not in sections:
                    sections[current_plan] = []
                    order.append(current_plan)
                in_table = False
            elif in_latest:
                # Capture date headers and bullet lines verbatim
                if line.startswith("**") or line.startswith("- "):
                    latest_updates.append(line)
            elif line.startswith("| #") or line.startswith("|---"):
                in_table = True
            elif in_table and current_plan and line.startswith("|"):
                sections[current_plan].append(line)
                # Parse serial and unit_id to rebuild serial tracking state
                cols = [c.strip() for c in line.split("|")]
                if len(cols) >= 3:
                    serial_str = cols[1]
                    unit_id    = cols[2]
                    if "." in serial_str:
                        # Sub-entry (e.g. "2.1") — track highest sub index
                        try:
                            sub = int(serial_str.split(".")[1])
                            unit_sub_counts[unit_id] = max(
                                unit_sub_counts.get(unit_id, 0), sub
                            )
                        except (ValueError, IndexError):
                            pass
                    elif serial_str.isdigit():
                        # Whole-number entry — this becomes the new base serial
                        # for this unit, resetting the sub-count
                        unit_base_serials[unit_id] = serial_str
                        unit_sub_counts[unit_id] = 0

    return sections, order, unit_base_serials, unit_sub_counts, latest_updates


def _write_sections(
    history_file: str,
    sections: dict,
    order: list,
    current_units: dict,
    latest_updates: list,
) -> None:
    """Writes the full history file with one table per plan, followed by a
    reverse-chronological Latest Updates section.

    Each plan heading includes a live count of currently available units,
    e.g. ``## Plan 1D (4 units available)``.
    """
    plan_counts: dict = {}
    for data in current_units.values():
        plan = data["plan"]
        plan_counts[plan] = plan_counts.get(plan, 0) + 1

    dir_name = os.path.dirname(history_file)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    with open(history_file, "w") as f:
        f.write("# Apartment Listings History\n\n")
        for plan in order:
            count = plan_counts.get(plan, 0)
            unit_word = "unit" if count == 1 else "units"
            f.write(f"## {plan} ({count} {unit_word} available)\n\n")
            f.write(_TABLE_HEADER)
            for row in sections[plan]:
                f.write(row + "\n")
            f.write("\n")

        if latest_updates:
            f.write(f"## {_LATEST_UPDATES_HEADING}\n\n")
            for line in latest_updates:
                f.write(line + "\n")
                # Blank line after each date header for readability
                if line.startswith("**"):
                    f.write("\n")
            f.write("\n")


def _is_blank(history_file: str) -> bool:
    """True when the history file is missing or contains no data rows."""
    if not os.path.exists(history_file):
        return True
    _, order, _, _, _ = _read_sections(history_file)
    return len(order) == 0


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------

def update_history(state_file: str, history_file: str, current_units: dict) -> list:
    """
    Compares current units against saved state, records changes into per-plan
    tables in the Markdown history, and saves the new state.

    Serial numbering rules:
      • A unit's first 🟢 Added event gets the next available whole number
        within its plan section (1, 2, 3 …).
      • All subsequent events for that unit (price change, date change, removed)
        receive nested serials under that same base: 2.1, 2.2, 2.3 …
      • If a unit is removed and later re-listed it is treated as a brand-new
        listing and receives a fresh whole number; any new sub-events nest
        under that new base.

    Each plan heading is annotated with the live count of currently available
    units, e.g. ``## Plan 1B (3 units available)``.

    The bottom of the file contains a ## Latest Updates section with one
    bullet per run (newest first), summarising all changes in plain English.

    Returns a list of human-readable change summary strings.
    """
    blank = _is_blank(history_file)

    if blank:
        sections: dict = {}
        order: list = []
        old_state: dict = {}
        unit_base_serials: dict = {}
        unit_sub_counts: dict = {}
        latest_updates: list = []
    else:
        sections, order, unit_base_serials, unit_sub_counts, latest_updates = (
            _read_sections(history_file)
        )
        old_state = {}
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                try:
                    old_state = json.load(f)
                except json.JSONDecodeError:
                    pass

    today_log  = datetime.now(tz=_PT).strftime("%b %d, %Y %H:%M PT")
    today_nice = datetime.now(tz=_PT).strftime("%B %d, %Y")  # e.g. "June 28, 2026"

    # Collect changes grouped by plan
    plan_changes: dict = {}

    for unit_id, data in current_units.items():
        plan = data["plan"]
        if unit_id not in old_state:
            deal  = _is_deal(data)
            n_cell = "**`{n}`**" if deal else "{n}"
            price  = data["price"]
            sqft   = data["sqft"]
            floor  = data["floor"]
            avail  = data["available"]
            entry = {
                "unit_id":    unit_id,
                "event_type": "added",
                "row_tpl":    f"| {n_cell} | {_hi(unit_id, deal)} | {sqft} | {floor} | {avail} | 🟢 Added | {_hi('Price: ' + price, deal)} | {today_log} |",
                "summary":    f"🟢 Added {unit_id} ({plan})",
                "statement":  f"{unit_id} ({plan}) **`listed`** at {price}",
            }
        elif _norm_price(old_state[unit_id].get("price", "")) != _norm_price(data["price"]):
            old_price = old_state[unit_id].get("price")
            deal  = _is_deal(data)
            n_cell = "**`{n}`**" if deal else "{n}"
            price  = data["price"]
            sqft   = data["sqft"]
            floor  = data["floor"]
            avail  = data["available"]
            entry = {
                "unit_id":    unit_id,
                "event_type": "price_changed",
                "row_tpl":    f"| {n_cell} | {_hi(unit_id, deal)} | {sqft} | {floor} | {avail} | 🟡 Price Changed | {_hi(str(old_price) + ' ➔ ' + price, deal)} | {today_log} |",
                "summary":    f"🟡 Price Changed {unit_id} ({plan})",
                "statement":  f"{unit_id} ({plan}) **`price changed`** from {old_price} to {price}",
            }
        elif old_state[unit_id].get("available") != data["available"]:
            old_date = old_state[unit_id].get("available")
            deal  = _is_deal(data)
            n_cell = "**`{n}`**" if deal else "{n}"
            price  = data["price"]
            sqft   = data["sqft"]
            floor  = data["floor"]
            avail  = data["available"]
            entry = {
                "unit_id":    unit_id,
                "event_type": "date_changed",
                "row_tpl":    f"| {n_cell} | {_hi(unit_id, deal)} | {sqft} | {floor} | {avail} | 🔵 Date Changed | {_hi(str(old_date) + ' ➔ ' + avail, deal)} | {today_log} |",
                "summary":    f"🔵 Date Changed {unit_id} ({plan})",
                "statement":  f"{unit_id} ({plan}) **`date changed`** from {old_date} to {avail}",
            }
        else:
            continue

        plan_changes.setdefault(plan, []).append(entry)

    for unit_id, data in old_state.items():
        if unit_id not in current_units:
            plan = data["plan"]
            entry = {
                "unit_id":    unit_id,
                "event_type": "removed",
                "row_tpl":    f"| {{n}} | {unit_id} | {data.get('sqft','?')} | {data.get('floor','?')} | {data.get('available','?')} | 🔴 Removed | Was {data.get('price')} | {today_log} |",
                "summary":    f"🔴 Removed {unit_id} ({plan})",
                "statement":  f"{unit_id} ({plan}) **`removed`** (was {data.get('price')})",
            }
            plan_changes.setdefault(plan, []).append(entry)

    summaries: list = []
    run_statements: list = []

    for plan in sorted(plan_changes.keys()):
        entries = sorted(plan_changes[plan], key=lambda e: e["unit_id"])

        if plan not in sections:
            sections[plan] = []
            order.append(plan)
        order[:] = sorted(order)

        # Next whole number = existing whole-number rows in this plan + 1
        next_whole = _count_whole_rows(sections[plan]) + 1

        for entry in entries:
            unit_id    = entry["unit_id"]
            event_type = entry["event_type"]

            if event_type == "added":
                serial = str(next_whole)
                unit_base_serials[unit_id] = serial
                unit_sub_counts[unit_id]   = 0
                next_whole += 1
            else:
                if unit_id in unit_base_serials:
                    sub = unit_sub_counts.get(unit_id, 0) + 1
                    unit_sub_counts[unit_id] = sub
                    serial = f"{unit_base_serials[unit_id]}.{sub}"
                else:
                    # No prior Added entry found — fall back to whole number
                    serial = str(next_whole)
                    unit_base_serials[unit_id] = serial
                    unit_sub_counts[unit_id]   = 0
                    next_whole += 1

            sections[plan].append(entry["row_tpl"].format(n=serial))
            summaries.append(entry["summary"])
            run_statements.append(entry["statement"])

    # Prepend a new date-grouped block to Latest Updates if anything changed this run
    if run_statements:
        # Insert in reverse order so index 0 ends up as the date header
        for stmt in reversed(run_statements):
            latest_updates.insert(0, f"- {stmt}")
        latest_updates.insert(0, f"**{today_nice}**")

    if sections:
        _write_sections(history_file, sections, order, current_units, latest_updates)

    with open(state_file, "w") as f:
        json.dump(current_units, f, indent=2)

    return summaries
