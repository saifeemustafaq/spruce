import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

TARGET_URL = "https://prometheusapartments.com/ca/sunnyvale-apartments/spruce"
KEYWORDS = ["1BMR", "2BMR"]
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

        # Wait for the pricing section to load
        try:
            page.wait_for_selector("#pricingAndFloorPlanBox", timeout=15000)
        except Exception:
            pass

        # Extra buffer for JS-rendered content
        page.wait_for_timeout(4000)

        content = page.inner_text("body")
        browser.close()
        return content


def send_alert(found_keywords):
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not app_password:
        print("ERROR: GMAIL_APP_PASSWORD secret is not set.")
        return

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = "BMR Listing Alert — Spruce Apartments Sunnyvale"

    body = (
        f"A BMR unit was spotted at Spruce Apartments!\n\n"
        f"Matched keywords: {', '.join(found_keywords)}\n\n"
        f"Check listings now:\n{TARGET_URL}\n"
    )
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, app_password)
        server.send_message(msg)


def main():
    print(f"Checking {TARGET_URL} for BMR listings...")
    content = scrape_page()

    found = [kw for kw in KEYWORDS if kw in content]

    if found:
        print(f"FOUND: {found} — sending email alert.")
        send_alert(found)
        print("Email sent to saifeemustafaq@gmail.com")
    else:
        print("No BMR listings found. Nothing to report.")


if __name__ == "__main__":
    main()
