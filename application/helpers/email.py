"""
Email helper for sending emails via SMTP in background threads.
"""
import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape
from application.helpers.logger import get_logger

logger = get_logger("email")

# SMTP Configuration
SMTP_SERVER = "smtpout.secureserver.net"
SMTP_PORT = 465
SENDER_EMAIL = os.getenv("SENDING_EMAIL")
SENDER_PASSWORD = os.getenv("SENDING_PASSWORD")
SENDER_NAME = os.getenv("SENDER_NAME", "RoadPulse")

# Jinja2 environment for email templates
template_env = Environment(
    loader=FileSystemLoader("application/templates/emails"),
    autoescape=select_autoescape(["html", "xml"])
)


def send_email(to_emails: List[str], subject: str, template_path: str, context: Dict) -> Tuple[bool, str]:
    """
    Send email using SMTP with HTML template.
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject line
        template_path: Path to Jinja2 template file (relative to templates/emails/)
        context: Dictionary of variables to render in template
    
    Returns:
        Tuple[bool, str]: (success, error_message)
    """
    try:
        # Load and render template
        template = template_env.get_template(template_path)
        html_content = template.render(**context)
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        message["To"] = ", ".join(to_emails)
        
        # Attach HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        # Send email via SMTP
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_emails, message.as_string())
        
        logger.info(f"Email Sent :: Subject -> {subject} :: Recipients -> {to_emails}")
        return True, ""
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Email Failed :: Subject -> {subject} :: Recipients -> {to_emails} :: Error -> {error_msg}")
        return False, error_msg


def send_email_in_background(to_emails: List[str], subject: str, template_path: str, context: Dict):
    """
    Fire-and-forget: sends emails in a background daemon thread.
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject line
        template_path: Path to Jinja2 template file
        context: Dictionary of variables to render in template
    """
    thread = threading.Thread(
        target=send_email,
        args=(to_emails, subject, template_path, context),
        daemon=True,
        name=f"email-{subject[:30]}"
    )
    thread.start()
    logger.info(f"Email Thread Started :: Subject -> {subject} :: Recipients -> {len(to_emails)} :: Thread -> {thread.name}")
