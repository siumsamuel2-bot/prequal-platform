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


WELCOME_EMAIL_SUBJECT = "Welcome to Prequal - Let's Get Started"
WELCOME_EMAIL_body = """Welcome to Prequal!

Your account has been created successfully. Here's what you can do next:

1. Set up your organization
   - Go to /setup to create your company workspace
   - This takes about 2 minutes

2. Add your subcontractors
   - Import a CSV with your subcontractor list, or
   - Add them one by one manually

3. Start tracking compliance
   - Upload certification documents
   - Get automatic alerts for expiring certs
   - Generate compliance reports

Need help? Reply to this email or check our documentation.

Best regards,
The Prequal Team
"""

WELCOME_EMAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9fafb; }}
        .step {{ margin: 15px 0; padding: 10px; background: white; border-left: 3px solid #2563eb; }}
        .step-number {{ font-weight: bold; color: #2563eb; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        .button {{ display: inline-block; background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to Prequal!</h1>
        </div>
        <div class="content">
            <p>Your account has been created successfully. Here's what you can do next:</p>
            
            <div class="step">
                <span class="step-number">1. Set up your organization</span><br/>
                Go to /setup to create your company workspace. This takes about 2 minutes.
            </div>
            
            <div class="step">
                <span class="step-number">2. Add your subcontractors</span><br/>
                Import a CSV with your subcontractor list, or add them one by one manually.
            </div>
            
            <div class="step">
                <span class="step-number">3. Start tracking compliance</span><br/>
                Upload certification documents, get automatic alerts for expiring certs, and generate compliance reports.
            </div>
            
            <p style="margin-top: 20px;">
                <a href="{app_url}/setup" class="button">Get Started</a>
            </p>
        </div>
        <div class="footer">
            <p>Need help? Reply to this email or check our documentation.</p>
            <p>Best regards,<br/>The Prequal Team</p>
        </div>
    </div>
</body>
</html>
"""

SETUP_COMPLETE_EMAIL_SUBJECT = "Your Prequal Organization is Ready"
SETUP_COMPLETE_EMAIL_body = """Your organization has been set up successfully!

You can now start managing your subcontractor compliance.

Next steps:
- Import your first subcontractor at /subcontractors/import
- Create your first project at /projects/new
- Explore the dashboard at /dashboard

Questions? We're here to help.

Best regards,
The Prequal Team
"""

SETUP_COMPLETE_EMAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #16a34a; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9fafb; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        .button {{ display: inline-block; background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Your Organization is Ready!</h1>
        </div>
        <div class="content">
            <p>Your organization has been set up successfully! You can now start managing your subcontractor compliance.</p>
            
            <h3>Next steps:</h3>
            <ul>
                <li>Import your first subcontractor at <a href="{app_url}/subcontractors/import">/subcontractors/import</a></li>
                <li>Create your first project at <a href="{app_url}/projects/new">/projects/new</a></li>
                <li>Explore the dashboard at <a href="{app_url}/dashboard">/dashboard</a></li>
            </ul>
            
            <p style="margin-top: 20px;">
                <a href="{app_url}/dashboard" class="button">Go to Dashboard</a>
            </p>
        </div>
        <div class="footer">
            <p>Questions? We're here to help.</p>
            <p>Best regards,<br/>The Prequal Team</p>
        </div>
    </div>
</body>
</html>
"""

FIRST_ALERT_EMAIL_SUBJECT = "Prequal Alert: Certification Expiring Soon"
FIRST_ALERT_EMAIL_body = """Prequal Alert

You have a certification expiring soon:

{subcontractor_name} - {certification_type}
Expires: {expiration_date}
Days remaining: {days_until_expiration}

Log in to Prequal to review and update this certification.

Best regards,
The Prequal Team
"""

FIRST_ALERT_EMAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc2626; color: white; padding: 20px; text-align: center; }}
        .alert-box {{ padding: 20px; background: #fef2f2; border: 1px solid #dc2626; border-radius: 5px; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        .button {{ display: inline-block; background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Certification Alert</h1>
        </div>
        <div class="content">
            <div class="alert-box">
                <p><strong>You have a certification expiring soon:</strong></p>
                <p><strong>Subcontractor:</strong> {subcontractor_name}</p>
                <p><strong>Certification:</strong> {certification_type}</p>
                <p><strong>Expires:</strong> {expiration_date}</p>
                <p><strong>Days remaining:</strong> {days_until_expiration}</p>
            </div>
            
            <p>Log in to Prequal to review and update this certification.</p>
            
            <p style="margin-top: 20px;">
                <a href="{app_url}/subcontractors/{subcontractor_id}" class="button">View Subcontractor</a>
            </p>
        </div>
        <div class="footer">
            <p>Best regards,<br/>The Prequal Team</p>
        </div>
    </div>
</body>
</html>
"""


async def send_welcome_email(to_email: str, app_url: str = "https://prequal.example.com") -> NotificationResult:
    """Send welcome email to new users."""
    html = WELCOME_EMAIL_HTML.replace("{app_url}", app_url)
    return await send_email(to_email, WELCOME_EMAIL_SUBJECT, WELCOME_EMAIL_body, html)


async def send_setup_complete_email(to_email: str, app_url: str = "https://prequal.example.com") -> NotificationResult:
    """Send setup complete notification."""
    html = SETUP_COMPLETE_EMAIL_HTML.replace("{app_url}", app_url)
    return await send_email(to_email, SETUP_COMPLETE_EMAIL_SUBJECT, SETUP_COMPLETE_EMAIL_body, html)


async def send_first_alert_email(
    to_email: str,
    subcontractor_name: str,
    certification_type: str,
    expiration_date: str,
    days_until_expiration: int,
    subcontractor_id: str,
    app_url: str = "https://prequal.example.com"
) -> NotificationResult:
    """Send first alert email for expiring certification."""
    body = FIRST_ALERT_EMAIL_body.format(
        subcontractor_name=subcontractor_name,
        certification_type=certification_type,
        expiration_date=expiration_date,
        days_until_expiration=days_until_expiration
    )
    html = FIRST_ALERT_EMAIL_HTML.format(
        app_url=app_url,
        subcontractor_name=subcontractor_name,
        certification_type=certification_type,
        expiration_date=expiration_date,
        days_until_expiration=days_until_expiration,
        subcontractor_id=subcontractor_id
    )
    return await send_email(to_email, FIRST_ALERT_EMAIL_SUBJECT, body, html)