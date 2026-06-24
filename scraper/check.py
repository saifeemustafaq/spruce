import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

TARGET_URL = "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce"
GMAIL_USER = "saifeemustafaq@gmail.com"
SNAPSHOT_PATH = "scraper/snapshot.txt"

# Set as a GitHub repo variable (Settings → Variables → Actions):
#   TRACKING_MODE = bmr      → only email when BMR/Income Limit unit appears
#   TRACKING_MODE = changes  → email whenever anything on the page changes
TRACKING_MODE = os.environ.get("TRACKING_MODE", "bmr").strip().lower()


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        try:
            page.wait_for_selector("#pricingAndFloorPlanBox", timeout=15000)
        except Exception:
            pass

        page.wait_for_timeout(4000)

        # Prefer just the pricing section to reduce noise from unrelated page areas
        try:
            content = page.locator("#pricingAndFloorPlanBox").inner_text(timeout=5000)
        except Exception:
            content = page.inner_text("body")

        browser.close()
        return content


def normalize(text):
    """Strip per-line whitespace and blank lines for stable comparison."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# BMR detection
# ---------------------------------------------------------------------------

def find_bmr_plans(text):
    sections = re.split(r'(?=\bPlan )', text)
    found = []
    for section in sections:
        has_bmr = "BMR" in section
        has_income = "Income Limit" in section
        if not has_bmr and not has_income:
            continue
        first_line = next(
            (l.strip() for l in section.splitlines() if l.strip()),
            section[:80]
        )
        found.append({
            "name":       first_line,
            "details":    section.strip(),
            "has_bmr":    has_bmr,
            "has_income": has_income,
        })
    return found


def classify(plan):
    if plan["has_bmr"] and plan["has_income"]:
        return "BMR + Income Limit"
    if plan["has_bmr"]:
        return "BMR"
    return "Income Limit"


# ---------------------------------------------------------------------------
# Snapshot (change detection)
# ---------------------------------------------------------------------------

def load_snapshot():
    if os.path.exists(SNAPSHOT_PATH):
        with open(SNAPSHOT_PATH) as f:
            return f.read()
    return None


def save_snapshot(text):
    with open(SNAPSHOT_PATH, "w") as f:
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
# Email
# ---------------------------------------------------------------------------

def send_email(subject, body):
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not app_password:
        print("ERROR: GMAIL_APP_PASSWORD secret is not set.")
        return
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, app_password)
        server.send_message(msg)
    print(f"  Email sent: {subject}")


def send_bmr_alert(plans):
    count = len(plans)
    unit_word = "unit" if count == 1 else "units"
    plan_lines = "\n\n".join(
        f"  [{classify(p)}] {p['name']}\n  {p['details'][:300]}"
        for p in plans
    )
    send_email(
        subject=f"BMR Alert — {count} {unit_word} available at Spruce Sunnyvale!",
        body=(
            f"{count} BMR / Income Limit {unit_word} just appeared at Spruce!\n\n"
            f"{plan_lines}\n\n"
            f"Apply now:\n{TARGET_URL}\n"
        ),
    )


def send_change_alert(added, removed, is_first_run):
    if is_first_run:
        send_email(
            subject="Spruce Tracker — Baseline snapshot saved (change detection ON)",
            body=(
                "First run in 'changes' mode complete.\n\n"
                "The current page content has been saved as the baseline. "
                "You'll get an email whenever anything changes on the listing page, "
                "showing exactly what was added or removed.\n\n"
                "To verify: compare the email diff against what you see on the site.\n"
                "Once satisfied, set TRACKING_MODE back to 'bmr'.\n\n"
                f"Listing page:\n{TARGET_URL}\n"
            ),
        )
        return

    added_section   = "\n".join(f"  + {l}" for l in added[:80])   or "  (nothing added)"
    removed_section = "\n".join(f"  - {l}" for l in removed[:80]) or "  (nothing removed)"
    send_email(
        subject=f"Spruce — Page changed (+{len(added)} / -{len(removed)} lines)",
        body=(
            f"Something changed on the Spruce listing page.\n\n"
            f"ADDED ({len(added)} lines):\n{added_section}\n\n"
            f"REMOVED ({len(removed)} lines):\n{removed_section}\n\n"
            f"Cross-check against the site:\n{TARGET_URL}\n"
        ),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Mode: {TRACKING_MODE}")
    print(f"Checking {TARGET_URL} ...")
    raw = scrape_page()
    text = normalize(raw)

    if TRACKING_MODE == "changes":
        old = load_snapshot()
        save_snapshot(text)

        if old is None:
            print("No previous snapshot found — saving baseline and emailing confirmation.")
            send_change_alert([], [], is_first_run=True)
        else:
            added, removed = compute_diff(old, text)
            if added or removed:
                print(f"Page changed: +{len(added)} lines / -{len(removed)} lines — sending email.")
                send_change_alert(added, removed, is_first_run=False)
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
