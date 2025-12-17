import os
import smtplib
from email.message import EmailMessage


def _as_bool(v: str) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def send_mail(to, subject: str, body: str, attachment_bytes: bytes, attachment_name: str):
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()

    smtp_from = os.environ.get("SMTP_FROM", "").strip() or smtp_user

    use_ssl = _as_bool(os.environ.get("SMTP_USE_SSL", "false"))
    use_starttls = _as_bool(os.environ.get("SMTP_USE_STARTTLS", "true"))

    if not smtp_host:
        raise RuntimeError("SMTP_HOST not set")
    if not smtp_user or not smtp_password:
        raise RuntimeError("SMTP_USER or SMTP_PASSWORD not set")
    if not smtp_from:
        raise RuntimeError("SMTP_FROM not set (and SMTP_USER empty)")

    # Normalize recipients
    if isinstance(to, str):
        recipients = [x.strip() for x in to.split(",") if x.strip()]
    else:
        recipients = list(to)

    if not recipients:
        raise RuntimeError("No recipients provided")

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)

    msg.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="pdf",
        filename=attachment_name,
    )

    # Connect
    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)

    try:
        server.ehlo()
        if use_starttls and not use_ssl:
            server.starttls()
            server.ehlo()

        server.login(smtp_user, smtp_password)

        # send_message returns dict of failures (empty dict = success)
        failures = server.send_message(msg)
        if failures:
            raise RuntimeError(f"SMTP refused some recipients: {failures}")

        print(f"Email sent OK to: {recipients}")
    finally:
        try:
            server.quit()
        except Exception:
            pass
