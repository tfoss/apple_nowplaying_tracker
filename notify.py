#!/usr/bin/env python3
"""
Error notification system for Apple TV tracker.

Sends email notifications when errors occur during scraping.
Uses Gmail SMTP with app password authentication.

Only sends notifications after CONSECUTIVE_FAILURES_THRESHOLD consecutive
failures for the same device, to avoid alerts for transient issues.

Required environment variables:
- NOTIFY_EMAIL_FROM: Gmail address to send from
- NOTIFY_EMAIL_PASSWORD: Gmail app password (not regular password)
- NOTIFY_EMAIL_TO: Email address to send notifications to (defaults to FROM)

To get a Gmail app password:
1. Go to https://myaccount.google.com/apppasswords
2. Create a new app password for "Mail"
3. Use that 16-character password in NOTIFY_EMAIL_PASSWORD
"""

import json
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

# Error tracking settings
CONSECUTIVE_FAILURES_THRESHOLD = 3  # Only notify after this many consecutive failures
ERROR_COOLDOWN_MINUTES = 60  # Don't send same error more than once per hour
ERROR_STATE_FILE = Path(__file__).parent / ".error_state.json"


def _load_error_state():
    """Load persistent error state from disk."""
    if ERROR_STATE_FILE.exists():
        try:
            with open(ERROR_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"failure_counts": {}, "last_notified": {}}


def _save_error_state(state):
    """Save error state to disk."""
    try:
        with open(ERROR_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"[NOTIFY] Failed to save error state: {e}")


def record_device_success(device_name: str):
    """Record a successful connection, resetting the failure count."""
    state = _load_error_state()
    error_key = f"device:{device_name}"
    if error_key in state["failure_counts"]:
        del state["failure_counts"][error_key]
        _save_error_state(state)


def record_device_error(device_name: str, error: str):
    """
    Record a device error and send notification if threshold reached.

    Returns True if notification was sent, False otherwise.
    """
    state = _load_error_state()
    error_key = f"device:{device_name}"

    # Increment failure count
    current_count = state["failure_counts"].get(error_key, 0) + 1
    state["failure_counts"][error_key] = current_count
    _save_error_state(state)

    print(
        f"[NOTIFY] {device_name}: failure {current_count}/{CONSECUTIVE_FAILURES_THRESHOLD}"
    )

    # Check if we've hit the threshold
    if current_count < CONSECUTIVE_FAILURES_THRESHOLD:
        return False

    # Check cooldown
    now = datetime.now()
    last_notified_str = state["last_notified"].get(error_key)
    if last_notified_str:
        last_notified = datetime.fromisoformat(last_notified_str)
        minutes_ago = (now - last_notified).total_seconds() / 60
        if minutes_ago < ERROR_COOLDOWN_MINUTES:
            print(f"[NOTIFY] Skipping notification (sent {minutes_ago:.0f}m ago)")
            return False

    # Send notification
    subject = f"Device Error: {device_name}"
    message = f"""
Apple TV Tracker encountered persistent errors with device: {device_name}

Time: {now.isoformat()}
Consecutive failures: {current_count}
Latest error: {error}

This may indicate:
- Device needs re-pairing (run: atvremote -s <IP> --protocol companion pair)
- Device is offline or unreachable
- Network connectivity issues

The device will not be tracked until this is resolved.
"""

    if _send_email(subject, message):
        state["last_notified"][error_key] = now.isoformat()
        _save_error_state(state)
        return True
    return False


def _send_email(subject: str, message: str):
    """Send an email notification."""
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print(f"[NOTIFY] Email not configured - would have sent: {subject}")
        return False

    try:
        msg = MIMEText(message)
        msg["Subject"] = f"[ATV Tracker] {subject}"
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        print(f"[NOTIFY] Sent notification: {subject}")
        return True

    except Exception as e:
        print(f"[NOTIFY] Failed to send notification: {e}")
        return False


def send_error_notification(subject: str, message: str, error_key: str = None):
    """
    Send an error notification email (legacy function for non-device errors).
    """
    return _send_email(subject, message)


def notify_device_error(device_name: str, error: str):
    """Record device error and notify if threshold reached."""
    return record_device_error(device_name, error)


def notify_script_error(script_name: str, error: str):
    """Send notification about a script-level error (immediate, no threshold)."""
    subject = f"Script Error: {script_name}"
    message = f"""
Apple TV Tracker script encountered an error.

Script: {script_name}
Time: {datetime.now().isoformat()}
Error: {error}

Please check the logs for more details.
"""
    return _send_email(subject, message)


def clear_error_state():
    """Clear all error state (for testing)."""
    if ERROR_STATE_FILE.exists():
        ERROR_STATE_FILE.unlink()
    print("[NOTIFY] Error state cleared")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear_error_state()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Testing notification system...")
        if EMAIL_FROM and EMAIL_PASSWORD:
            _send_email(
                "Test Notification",
                "This is a test notification from the Apple TV tracker.",
            )
        else:
            print(
                "Email not configured. Set NOTIFY_EMAIL_FROM and NOTIFY_EMAIL_PASSWORD in .env"
            )
            print(f"Notifications would be sent to: {EMAIL_TO}")
    else:
        print("Usage:")
        print("  python notify.py --test   # Send a test email")
        print("  python notify.py --clear  # Clear error state")
        print()
        state = _load_error_state()
        print(f"Current failure counts: {state['failure_counts']}")
        print(f"Last notified: {state['last_notified']}")
