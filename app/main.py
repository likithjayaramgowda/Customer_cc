import os

from app.payload import load_event, parse_submission
from app.pdf_report import build_pdf_bytes, build_pdf_bytes_dynamic
from app.mailer import send_mail
from app.metadata import append_metadata_row
from app.id_generator import next_complaint_id
from app.dropbox_uploader import upload_pdf_to_dropbox


def _get_value_from_sections(sections, wanted_labels):
    """
    sections format:
    [
      {"title": "...", "rows": [{"label": "...", "value": "..."}, ...]},
      ...
    ]
    """
    if not sections:
        return ""
    wanted = {w.strip().lower() for w in wanted_labels}
    for sec in sections:
        for row in sec.get("rows", []):
            label = str(row.get("label", "")).strip().lower()
            if label in wanted:
                return str(row.get("value", "")).strip()
    return ""


def _derive_customer_email(submission) -> str:
    # Prefer common keys in fields
    for k in ("customer_email", "Email Address", "Email", "Customer Email"):
        v = submission.fields.get(k)
        if v:
            return str(v).strip()

    # Fall back to sections (this is where your real labels usually live)
    return _get_value_from_sections(
        submission.sections,
        ["Email Address", "Email", "Customer Email", "E-mail"],
    )


def main():
    # Load GitHub repository_dispatch event
    event = load_event()
    submission = parse_submission(event)

    # ---- Complaint ID + PDF name (always auto) ----
    complaint_id = next_complaint_id(submission.timestamp)
    filename = f"{complaint_id}.pdf"

    # ---- Derived values ----
    title = f"{submission.form_title} – Complaint Report"

    subject = os.environ.get(
        "MAIL_SUBJECT",
        f"{submission.form_title} – Complaint {complaint_id}",
    )

    body = os.environ.get(
        "MAIL_BODY",
        "Please find attached the generated complaint PDF.",
    )

    # ---- PDF generation ----
    if submission.sections:
        pdf_bytes = build_pdf_bytes_dynamic(
            title=title,
            complaint_id=complaint_id,
            timestamp=submission.timestamp,
            status=submission.status,
            sections=submission.sections,
        )
    else:
        pdf_bytes = build_pdf_bytes(
            title=title,
            fields={
                "complaint_id": complaint_id,
                "timestamp": submission.timestamp,
                **submission.fields,
            },
        )

    # Write a local copy for debugging / workflow artifacts
    os.makedirs("out", exist_ok=True)
    with open(os.path.join("out", filename), "wb") as f:
        f.write(pdf_bytes)

    # ---- Build recipients (FORCE lab + customer) ----
    lab_email = os.environ.get("LAB_EMAIL", "").strip()
    customer_email = _derive_customer_email(submission)

    recipients = []
    if lab_email:
        recipients.append(lab_email)
    if customer_email and customer_email not in recipients:
        recipients.append(customer_email)

    # If still empty, fall back to whatever parse_submission provided
    if not recipients:
        if isinstance(submission.email_to, list):
            recipients = submission.email_to
        elif isinstance(submission.email_to, str) and submission.email_to.strip():
            recipients = [x.strip() for x in submission.email_to.split(",") if x.strip()]

    print(f"[INFO] Email recipients: {recipients}")

    # ---- Send email (DO NOT BLOCK PIPELINE IF IT FAILS) ----
    mail_ok = True
    mail_error = ""

    try:
        send_mail(
            to=recipients,
            subject=subject,
            body=body,
            attachment_bytes=pdf_bytes,
            attachment_name=filename,
        )
        print("Email sent OK")
    except Exception as e:
        mail_ok = False
        mail_error = str(e)
        print(f"[WARN] Email failed but continuing: {e}")

    # ---- Upload to Dropbox (also non-blocking) ----
    dropbox_path = ""
    dropbox_link = ""
    dropbox_ok = True
    dropbox_error = ""

    try:
        dropbox_path, dropbox_link = upload_pdf_to_dropbox(
            pdf_bytes=pdf_bytes,
            filename=filename,
        )
        print(f"Dropbox upload OK: {dropbox_path}")
        if dropbox_link:
            print(f"Dropbox link: {dropbox_link}")
    except Exception as e:
        dropbox_ok = False
        dropbox_error = str(e)
        print(f"[WARN] Dropbox upload failed but continuing: {e}")

    # ---- Append metadata CSV (always attempt)
