"""
Email sender for news digest delivery.

Supports Gmail SMTP with app password authentication.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Gmail SMTP configuration
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def get_email_config() -> dict:
    """Load email configuration from environment."""
    return {
        "recipient": os.getenv("EMAIL_RECIPIENT"),
        "gmail_user": os.getenv("GMAIL_USER"),
        "gmail_password": os.getenv("GMAIL_APP_PASSWORD"),
    }


def validate_config(config: dict) -> bool:
    """Check if all required email config is present."""
    required = ["recipient", "gmail_user", "gmail_password"]
    missing = [k for k in required if not config.get(k)]

    if missing:
        logger.error(f"Missing email config: {', '.join(missing)}")
        logger.error("Set these in .env: EMAIL_RECIPIENT, GMAIL_USER, GMAIL_APP_PASSWORD")
        return False

    return True


def send_gmail(
    to: str,
    subject: str,
    html_body: str,
    plain_body: str | None = None,
) -> bool:
    """
    Send email via Gmail SMTP.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_body: HTML content.
        plain_body: Plain text fallback (optional).

    Returns:
        True if sent successfully.
    """
    config = get_email_config()

    if not validate_config(config):
        return False

    gmail_user = config["gmail_user"]
    gmail_password = config["gmail_password"]

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to

    # Plain text fallback
    if plain_body:
        msg.attach(MIMEText(plain_body, "plain"))

    # HTML content
    msg.attach(MIMEText(html_body, "html"))

    try:
        logger.info(f"Connecting to {SMTP_HOST}:{SMTP_PORT}...")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.send_message(msg)

        logger.info(f"Email sent to {to}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Gmail auth failed: {e}")
        logger.error("Ensure you're using an App Password, not your regular password")
        logger.error("Create one at: https://myaccount.google.com/apppasswords")
        return False

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_digest(html_body: str) -> bool:
    """
    Send the news digest email.

    Args:
        html_body: HTML content of the digest.

    Returns:
        True if sent successfully.
    """
    config = get_email_config()

    if not validate_config(config):
        return False

    today = datetime.now().strftime("%B %d, %Y")
    subject = f"Daily News Digest - {today}"

    return send_gmail(
        to=config["recipient"],
        subject=subject,
        html_body=html_body,
    )


def test_mode():
    """Test email sending with a simple message."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("Testing email sender...\n")

    config = get_email_config()

    if not validate_config(config):
        print("\nTest FAILED: Missing configuration")
        return

    print(f"Recipient: {config['recipient']}")
    print(f"Sender: {config['gmail_user']}")

    test_html = """
    <html>
    <body>
        <h1>Test Email</h1>
        <p>This is a test email from the News Digest Agent.</p>
        <p>If you received this, email sending is working correctly!</p>
    </body>
    </html>
    """

    success = send_gmail(
        to=config["recipient"],
        subject="News Digest Agent - Test Email",
        html_body=test_html,
        plain_body="This is a test email from the News Digest Agent.",
    )

    if success:
        print("\nTest PASSED: Email sent successfully!")
    else:
        print("\nTest FAILED: Could not send email")


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        test_mode()
    else:
        print("Usage: python sender.py --test")
