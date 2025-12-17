import os

from app.payload import load_event, parse_submission
from app.pdf_report import build_pdf_bytes, build_pdf_bytes_dynamic
from app.mailer import send_mail
from app.metadata import append_metadata_row
from app.id_generator import next_complaint_id
from app.dropbox_uploader import upload_pdf_to_dropbox


def main():
    # Load GitHub repository_dispatch event
    event = load_event()
    submission = parse_submission(event)

    # ---- Complaint ID + PDF name (always auto) ----
    complaint_id = next_complaint_id(submission.timestamp)
    pdf_filename = f"{complaint_id}.pdf"

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

    filename = pdf_filename

    # ---- PDF generation ----
    if submission.sections:
        # Fully dynamic, form-driven PDF
        pdf_bytes = build_pdf_bytes_dynamic(
            title=title,
            complaint_id=complaint_id,
            timestamp=submission.timestamp,
            status=submission.status,
            sections=submission.sections,
        )
    else:
        # Legacy fallback (safe)
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

    # ---- Send email (DO NOT BLOCK PIPELINE IF IT FAILS) ----
    mail_ok = True
    mail_error = ""

    try:
        send_mail(
            to=submission.email_to,  # compulsory form email
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

    try:
        dropbox_path, dropbox_link = upload_pdf_to_dropbox(
            pdf_bytes=pdf_bytes,
            filename=filename,
        )
        print(f"Dropbox upload OK: {dropbox_path}")
        if dropbox_link:
            print(f"Dropbox link: {dropbox_link}")
    except Exception as e:
        print(f"[WARN] Dropbox upload failed but continuing: {e}")

    # ---- Append metadata CSV (always attempt) ----
    # We store mail result in fields so metadata captures pipeline health too
    fields_with_status = {
        **submission.fields,
        "mail_ok": mail_ok,
        "mail_error": mail_error,
    }

    append_metadata_row(
        complaint_id=complaint_id,
        submission_timestamp=submission.timestamp,
        recipients=submission.email_to,
        fields=fields_with_status,
        pdf_filename=filename,
        dropbox_file_path=dropbox_path,
        dropbox_shared_link=dropbox_link,
        github_run_url=os.environ.get("GITHUB_RUN_URL", ""),
        sections=submission.sections,   # <-- REQUIRED
    )



if __name__ == "__main__":
    main()
