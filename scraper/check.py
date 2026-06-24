import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

TARGET_URL = "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce"
GMAIL_USER = "saifeemustafaq@gmail.com"


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
        content = page.inner_text("body")
        browser.close()
        return content


def find_bmr_plans(text):
    """
    Split page text into per-plan blocks and tag each one.

    The Spruce website only lists AVAILABLE units, so if a plan block
    contains 'BMR' or 'Income Limit', that unit is available right now.

    Returns a list of dicts:
        {
            "name":         "Plan 1D-BMR (Income Limit)",
            "details":      <raw block text>,
            "has_bmr":      True/False,
            "has_income":   True/False,
        }
    """
    sections = re.split(r'(?=\bPlan )', text)

    found = []
    for section in sections:
        has_bmr = "BMR" in section
        has_income = "Income Limit" in section

        if not has_bmr and not has_income:
            continue

        first_line = next(
            (line.strip() for line in section.splitlines() if line.strip()),
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


def send_alert(plans):
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not app_password:
        print("ERROR: GMAIL_APP_PASSWORD secret is not set.")
        return

    count = len(plans)
    unit_word = "unit" if count == 1 else "units"

    plan_lines = "\n\n".join(
        f"  [{classify(p)}] {p['name']}\n  {p['details'][:300]}"
        for p in plans
    )

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = (
        f"BMR Alert — {count} {unit_word} available at Spruce Apartments Sunnyvale!"
    )

    body = (
        f"{count} BMR / Income Limit {unit_word} just appeared at Spruce!\n\n"
        f"{plan_lines}\n\n"
        f"Apply now:\n{TARGET_URL}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, app_password)
        server.send_message(msg)


def main():
    print(f"Checking {TARGET_URL} ...")
    text = scrape_page()

    plans = find_bmr_plans(text)

    if plans:
        for p in plans:
            print(f"  FOUND [{classify(p)}]: {p['name']}")
        send_alert(plans)
        print("Email alert sent to saifeemustafaq@gmail.com")
    else:
        print("No BMR or Income Limit listings found. No alert sent.")


if __name__ == "__main__":
    main()
