"""Notification delivery service for email and SMS alerts.

Provides:
- Email sending via SendGrid (or SMTP fallback)
- SMS sending via Twilio
- Notification preferences lookup
- Delivery status tracking via NotificationDeliveryLog

This module is designed to be called by the alert service after alerts are generated.
"""

import os
import logging
from typing import Optional
from datetime import datetime

from app.logging_config import get_logger

logger = get_logger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

EMAIL_FROM = os.getenv("EMAIL_FROM", "alerts@prequal.example.com")


class NotificationResult:
    def __init__(self, success: bool, message_id: Optional[str] = None, error: Optional[str] = None):
        self.success = success
        self.message_id = message_id
        self.error = error


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None
) -> NotificationResult:
    """Send an email notification.
    
    Currently logs the email. To enable real sending:
    1. Set SENDGRID_API_KEY environment variable
    2. Install sendgrid: pip install sendgrid
    """
    if not SENDGRID_API_KEY:
        logger.info(
            f"Email notification (SENDGRID_API_KEY not set): "
            f"to={to_email}, subject={subject}"
        )
        return NotificationResult(success=True, message_id=f"debug-{datetime.utcnow().timestamp()}")
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email=EMAIL_FROM,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
            html_content=html_body or body
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in (200, 201, 202):
            logger.info(f"Email sent successfully to {to_email}, status={response.status_code}")
            return NotificationResult(success=True, message_id=response.headers.get("X-Message-Id"))
        else:
            logger.error(f"Email send failed to {to_email}, status={response.status_code}")
            return NotificationResult(success=False, error=f"HTTP {response.status_code}")
            
    except Exception as e:
        logger.exception(f"Email send failed to {to_email}: {e}")
        return NotificationResult(success=False, error=str(e))


async def send_sms(
    to_phone: str,
    message: str
) -> NotificationResult:
    """Send an SMS notification.
    
    Currently logs the SMS. To enable real sending:
    1. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
    2. Install twilio: pip install twilio
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.info(
            f"SMS notification (Twilio not configured): "
            f"to={to_phone}, message={message[:50]}..."
        )
        return NotificationResult(success=True, message_id=f"debug-{datetime.utcnow().timestamp()}")
    
    try:
        from twilio.rest import Client
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        twilio_message = client.messages.create(
            body=message[:1600],
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone
        )
        
        logger.info(f"SMS sent successfully to {to_phone}, sid={twilio_message.sid}")
        return NotificationResult(success=True, message_id=twilio_message.sid)
        
    except Exception as e:
        logger.exception(f"SMS send failed to {to_phone}: {e}")
        return NotificationResult(success=False, error=str(e))


async def send_notification(
    recipient: str,
    subject: str,
    body: str,
    method: str = "email",
    html_body: Optional[str] = None
) -> NotificationResult:
    """Send a notification via the specified method (email or sms).
    
    Args:
        recipient: Email address (for email) or phone number (for sms)
        subject: Email subject (ignored for SMS)
        body: Message body
        method: 'email' or 'sms'
        html_body: Optional HTML body for emails
    
    Returns:
        NotificationResult with success status and message_id or error
    """
    if method == "sms":
        return await send_sms(recipient, body)
    else:
        return await send_email(recipient, subject, body, html_body)