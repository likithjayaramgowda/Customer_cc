import os
import smtplib
from email.message import EmailMessage
from typing import List


def send_mail(
    to: List[str],
    subject: str,
    body: str,
    attachment_bytes: bytes,
    attachment_name: str,
):
    if not to:
        raise ValueError("No recipients provided for email.")

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM", smtp_user)
    from_addr = os.environ.get("SMTP_FROM") 


    # SMTP2GO supports multiple connection modes. Make this configurable
    # so the workflow doesn't report success while the server drops the mail.
    smtp_use_ssl = (os.environ.get("SMTP_USE_SSL", "").strip().lower() in {"1", "true", "yes", "y"})
    smtp_use_starttls = (os.environ.get("SMTP_USE_STARTTLS", "true").strip().lower() in {"1", "true", "yes", "y"})

    if not smtp_user or not smtp_password:
        raise RuntimeError("SMTP_USER or SMTP_PASSWORD not set.")

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)

    msg.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="pdf",
        filename=attachment_name,
    )

    if smtp_use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port)

    try:
        server.ehlo()
        if (not smtp_use_ssl) and smtp_use_starttls:
            server.starttls()
            server.ehlo()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass
