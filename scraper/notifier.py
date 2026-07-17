import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import GMAIL_USER, GMAIL_APP_PASSWORD

_REPO = "https://github.com/saifeemustafaq/spruce"


def history_url(group_key: str, key: str) -> str:
    """GitHub blob link to a property's history file."""
    return f"{_REPO}/blob/main/scraper/data/{group_key}/{key}/listings_history.md"


def _deal_labels(data: dict) -> str:
    """Human labels for why a normalized unit counts as a deal."""
    labels = []
    if data.get("is_bmr"):
        labels.append("BMR")
    if data.get("is_income_limited"):
        labels.append("Income Limit")
    if data.get("is_deal") and not (data.get("is_bmr") or data.get("is_income_limited")):
        labels.append("Under $3k")
    return " + ".join(labels) if labels else "Deal"


def send_email(subject, body):
    if not GMAIL_APP_PASSWORD:
        print("ERROR: GMAIL_APP_PASSWORD secret is not set.")
        return
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"  Email sent: {subject}")


def send_api_error_alert(error: Exception, property_name: str, page_url: str) -> None:
    send_email(
        subject=f"⚠️ {property_name} Tracker — API failure, check required",
        body=(
            "The listing source could not be reached or returned unexpected data.\n\n"
            f"Property   : {property_name}\n"
            f"Error type : {type(error).__name__}\n"
            f"Details    :\n{error}\n\n"
            "Possible causes:\n"
            "  • The API endpoint URL changed\n"
            "  • The server returned an HTTP error (4xx / 5xx)\n"
            "  • The response format changed (no longer a JSON array)\n"
            "  • A network/firewall issue in GitHub Actions\n\n"
            f"Verify manually:\n{page_url}\n\n"
            "No listings_history.md changes were made during this run."
        ),
    )


def send_api_empty_alert(api_url: str, property_name: str, page_url: str) -> None:
    send_email(
        subject=f"⚠️ {property_name} Tracker — API returned 0 units",
        body=(
            "The listing source returned an empty list this run.\n\n"
            f"Property : {property_name}\n\n"
            "This could mean:\n"
            "  • All units are currently leased (no availability)\n"
            "  • The API date parameter or endpoint changed\n"
            "  • A temporary server-side issue\n\n"
            f"API URL used : {api_url}\n"
            f"Listing page : {page_url}\n\n"
            "No listings_history.md changes were made during this run.\n"
            "If units are visible on the website but this alert keeps firing, "
            "the API URL may need to be updated in config.py."
        ),
    )


def send_history_update_alert(changes: list, property_name: str, page_url: str, hist_url: str) -> None:
    added   = [c for c in changes if "Added"         in c]
    removed = [c for c in changes if "Removed"       in c]
    priced  = [c for c in changes if "Price Changed" in c]
    dated   = [c for c in changes if "Date Changed"  in c]

    def section(label, items):
        return (f"{label} ({len(items)}):\n" + "\n".join(f"  {c}" for c in items) + "\n") if items else ""

    body = (
        f"{len(changes)} change(s) were recorded for {property_name} this run.\n\n"
        + section("🟢 Added",         added)
        + section("🔴 Removed",       removed)
        + section("🟡 Price Changed", priced)
        + section("🔵 Date Changed",  dated)
        + f"\nFull history: {hist_url}\n"
        + f"Listing page: {page_url}\n"
    )

    unit_word = "change" if len(changes) == 1 else "changes"
    send_email(
        subject=f"{property_name} Tracker — {len(changes)} listing {unit_word} recorded",
        body=body,
    )


def send_bmr_alert(deals, property_name: str, page_url: str):
    """Alert for deal units. ``deals`` is a list of ``(unit_id, normalized_data)``
    tuples where each unit already carries is_bmr / is_income_limited / is_deal."""
    count = len(deals)
    unit_word = "unit" if count == 1 else "units"
    plan_lines = "\n\n".join(
        f"  [{_deal_labels(data)}] {unit_id} — {data.get('plan', '')}\n"
        f"  {data.get('price', '')} · {data.get('available', '')} · "
        f"{data.get('bedrooms', '')}BR/{data.get('bathrooms', '')}BA"
        for unit_id, data in deals
    )
    send_email(
        subject=f"🚨 ACT NOW — {count} BMR or Deal {unit_word} AVAILABLE at {property_name}!",
        body=(
            "=" * 60 + "\n"
            "🚨🚨🚨  BMR / DEAL UNIT AVAILABLE — APPLY IMMEDIATELY  🚨🚨🚨\n"
            "=" * 60 + "\n\n"
            f"{count} BMR, Income Limit, or price-deal {unit_word} "
            "(studio/1BR under $3k · 2BR+ incl. 2B-with-Den & 3BR under $4k) "
            f"just appeared at {property_name}.\n"
            "These go FAST. Stop what you are doing and apply NOW.\n\n"
            "--- UNIT DETAILS ---\n\n"
            f"{plan_lines}\n\n"
            "--- APPLY HERE ---\n"
            f"{page_url}\n\n"
            "=" * 60 + "\n"
            f"This is an automated alert from your {property_name} tracker.\n"
            "=" * 60 + "\n"
        ),
    )


def send_change_alert(added, removed, is_first_run, property_name: str, page_url: str, changes_log=None):
    if is_first_run:
        # Silently return on first run without sending a baseline email
        return

    added_section   = "\n".join(f"  + {l}" for l in added[:80])   or "  (nothing added)"
    removed_section = "\n".join(f"  - {l}" for l in removed[:80]) or "  (nothing removed)"

    log_section = ""
    if changes_log:
        log_section = "Specific unit changes detected:\n" + "\n".join(changes_log) + "\n\n"

    send_email(
        subject=f"{property_name} — Page changed (+{len(added)} / -{len(removed)} lines)",
        body=(
            f"Something changed on the {property_name} listing page.\n\n"
            f"{log_section}"
            f"ADDED ({len(added)} lines):\n{added_section}\n\n"
            f"REMOVED ({len(removed)} lines):\n{removed_section}\n\n"
            f"Cross-check against the site:\n{page_url}\n"
            f"Or view history log in your repo: listings_history.md"
        ),
    )


def send_store_error_alert(error: str, group_name: str, property_name: str) -> None:
    """Non-fatal notice that the MongoDB mirror failed for a property.

    The JSON/Markdown files remain the source of truth, so the run itself still
    succeeded — this just flags that Mongo is behind and may need a re-seed.
    """
    send_email(
        subject=f"⚠️ MongoDB mirror failed — {group_name} / {property_name}",
        body=(
            "The scraper wrote the authoritative JSON/Markdown files "
            "successfully, but the best-effort MongoDB mirror failed.\n\n"
            f"Group    : {group_name}\n"
            f"Property : {property_name}\n"
            f"Error    : {error}\n\n"
            "The dashboard may be stale until the next successful run. If this "
            "persists, check MONGODB_URI / Atlas network access, then rebuild "
            "from files with `npm run seed` in the bmr project."
        ),
    )
