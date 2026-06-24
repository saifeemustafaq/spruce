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

        # Extra buffer for JS-rendered content to fully settle
        page.wait_for_timeout(4000)

        content = page.inner_text("body")
        browser.close()
        return content


def find_available_bmr_plans(text):
    """
    Split page text into per-plan blocks and return any BMR (Income Limit)
    plans that are NOT marked 'Not Available'.

    Real page structure per plan:
        Plan 1D-BMR (Income Limit)
        $2,618
        1 Bed
        1 Bath
        676 Sq Ft
        View Plan 1D-BMR (Income Limit) Floor Plan Details
        Not Available          <-- we alert when this line is absent
    """
    # Each plan block starts with "Plan "
    sections = re.split(r'(?=\bPlan )', text)

    available = []
    for section in sections:
        if "BMR (Income Limit)" not in section:
            continue
        if "Not Available" in section:
            continue

        # Grab the plan name from the first non-empty line
        first_line = next(
            (line.strip() for line in section.splitlines() if line.strip()),
            section[:60]
        )
        available.append((first_line, section.strip()))

    return available


def send_alert(available_plans):
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not app_password:
        print("ERROR: GMAIL_APP_PASSWORD secret is not set.")
        return

    count = len(available_plans)
    unit_word = "unit" if count == 1 else "units"

    plan_details = "\n\n".join(
        f"  {name}\n  {details[:300]}"
        for name, details in available_plans
    )

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = (
        f"BMR Alert — {count} {unit_word} available at Spruce Apartments Sunnyvale!"
    )

    body = (
        f"{count} BMR (Income Limit) {unit_word} just became available at Spruce!\n\n"
        f"{plan_details}\n\n"
        f"Apply now:\n{TARGET_URL}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, app_password)
        server.send_message(msg)


def main():
    print(f"Checking {TARGET_URL} ...")
    text = scrape_page()

    available = find_available_bmr_plans(text)

    if available:
        names = [name for name, _ in available]
        print(f"AVAILABLE BMR PLANS FOUND: {names}")
        send_alert(available)
        print("Email alert sent to saifeemustafaq@gmail.com")
    else:
        print("All BMR (Income Limit) plans are currently 'Not Available'. No alert sent.")


if __name__ == "__main__":
    main()
