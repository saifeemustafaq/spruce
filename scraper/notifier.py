import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import GMAIL_USER, GMAIL_APP_PASSWORD, SPRUCE_PAGE_URL as TARGET_URL
from .parser import classify

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

def send_change_alert(added, removed, is_first_run, changes_log=None):
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
    
    log_section = ""
    if changes_log:
        log_section = "Specific unit changes detected:\n" + "\n".join(changes_log) + "\n\n"

    send_email(
        subject=f"Spruce — Page changed (+{len(added)} / -{len(removed)} lines)",
        body=(
            f"Something changed on the Spruce listing page.\n\n"
            f"{log_section}"
            f"ADDED ({len(added)} lines):\n{added_section}\n\n"
            f"REMOVED ({len(removed)} lines):\n{removed_section}\n\n"
            f"Cross-check against the site:\n{TARGET_URL}\n"
            f"Or view history log in your repo: listings_history.md"
        ),
    )
