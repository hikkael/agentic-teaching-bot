import os
import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SENDER  = os.getenv("EMAIL_SENDER")
PASSWORD = os.getenv("EMAIL_PASSWORD")


async def send_email(to: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email via Gmail SMTP.

    Args:
        to:      Recipient email address
        subject: Email subject line
        body:    Plain text email body

    Returns:
        True if sent successfully, False otherwise.
    """
    if not SENDER or not PASSWORD:
        logger.error("EMAIL_SENDER or EMAIL_PASSWORD not set in .env")
        return False

    # Build the email message
    msg = MIMEMultipart()
    msg["From"]    = SENDER
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,          # upgrades plain connection to TLS
            username=SENDER,
            password=PASSWORD,
        )
        logger.info(f"Email sent successfully to {to}")
        return True

    except aiosmtplib.SMTPAuthenticationError as e:
        logger.error(f"Gmail authentication failed: {e}")
        return False

    except Exception as e:
        logger.error(f"Failed to send email: {type(e).__name__}: {e}")
        return False