#!/usr/bin/env python3
"""
Error notification system for Apple TV tracker.

Sends email notifications when errors occur during scraping.
Uses Gmail SMTP with app password authentication.

Required environment variables:
- NOTIFY_EMAIL_FROM: Gmail address to send from
- NOTIFY_EMAIL_PASSWORD: Gmail app password (not regular password)
- NOTIFY_EMAIL_TO: Email address to send notifications to (defaults to FROM)

To get a Gmail app password:
1. Go to https://myaccount.google.com/apppasswords
2. Create a new app password for "Mail"
3. Use that 16-character password in NOTIFY_EMAIL_PASSWORD
"""

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = os.environ.get("NOTIFY_EMAIL_FROM")
EMAIL_PASSWORD = os.environ.get("NOTIFY_EMAIL_PASSWORD")
EMAIL_TO = os.environ.get("NOTIFY_EMAIL_TO", "ted.foss.spamfree@gmail.com")

# Track recent errors to avoid spam (in-memory, resets on restart)
_recent_errors = {}
ERROR_COOLDOWN_MINUTES = 60  # Don't send same error more than once per hour


def send_error_notification(subject: str, message: str, error_key: str = None):
    """
    Send an error notification email.

    Args:
        subject: Email subject line
        message: Email body text
        error_key: Optional key to dedupe errors (prevents spam for recurring issues)
    """
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print(f"[NOTIFY] Email not configured - would have sent: {subject}")
        return False

    # Check cooldown for this error type
    if error_key:
        now = datetime.now()
        last_sent = _recent_errors.get(error_key)
        if last_sent:
            minutes_ago = (now - last_sent).total_seconds() / 60
            if minutes_ago < ERROR_COOLDOWN_MINUTES:
                print(
                    f"[NOTIFY] Skipping notification (sent {minutes_ago:.0f}m ago): {subject}"
                )
                return False
        _recent_errors[error_key] = now

    try:
        # Build email
        msg = MIMEText(message)
        msg["Subject"] = f"[ATV Tracker] {subject}"
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        # Send via Gmail SMTP
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        print(f"[NOTIFY] Sent notification: {subject}")
        return True

    except Exception as e:
        print(f"[NOTIFY] Failed to send notification: {e}")
        return False


def notify_device_error(device_name: str, error: str):
    """Send notification about a device connection/scraping error."""
    subject = f"Device Error: {device_name}"
    message = f"""
Apple TV Tracker encountered an error with device: {device_name}

Time: {datetime.now().isoformat()}
Error: {error}

This may indicate:
- Device needs re-pairing (run: atvremote -s <IP> --protocol companion pair)
- Device is offline or unreachable
- Network connectivity issues

The device will not be tracked until this is resolved.
"""
    return send_error_notification(subject, message, error_key=f"device:{device_name}")


def notify_script_error(script_name: str, error: str):
    """Send notification about a script-level error."""
    subject = f"Script Error: {script_name}"
    message = f"""
Apple TV Tracker script encountered an error.

Script: {script_name}
Time: {datetime.now().isoformat()}
Error: {error}

Please check the logs for more details.
"""
    return send_error_notification(subject, message, error_key=f"script:{script_name}")


if __name__ == "__main__":
    # Test the notification system
    print("Testing notification system...")
    if EMAIL_FROM and EMAIL_PASSWORD:
        send_error_notification(
            "Test Notification",
            "This is a test notification from the Apple TV tracker.",
            error_key="test",
        )
    else:
        print(
            "Email not configured. Set NOTIFY_EMAIL_FROM and NOTIFY_EMAIL_PASSWORD in .env"
        )
        print(f"Notifications would be sent to: {EMAIL_TO}")
