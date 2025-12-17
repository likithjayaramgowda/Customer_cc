import csv
import json
import os
from datetime import datetime, timezone

CSV_PATH = "data/complaints_metadata.csv"

# Fixed schema (DO NOT reorder once in production)
CSV_FIELDS = [
    "complaint_id",
    "submission_timestamp",
    "created_at_utc",
    "recipients",
    "customer_email",
    "country",
    "product_name",
    "lot_serial_no",
    "complaint_type",
    "pdf_filename",
    "dropbox_file_path",
    "dropbox_shared_link",
    "github_run_url",
    "all_fields_kv",
]


# Map normalized CSV columns → possible form field names
FIELD_ALIASES = {
    "customer_email": ["Email Address", "Email", "Customer Email"],
    "country": ["Country"],
    "product_name": ["Product Name"],
    "lot_serial_no": ["LOT / Serial Number", "Lot / Serial Number"],
    "complaint_type": ["Complaint Type"],
}


def _extract_normalized_fields(fields: dict) -> dict:
    """
    Pull known fields into fixed CSV columns.
    Everything else stays in all_fields_kv.
    """
    normalized = {}

    for csv_col, aliases in FIELD_ALIASES.items():
        value = ""
        for key in aliases:
            if key in fields and fields[key]:
                value = fields[key]
                break
        normalized[csv_col] = value

    return normalized


def append_metadata_row(
    complaint_id: str,
    submission_timestamp: str,
    recipients,
    fields: dict,
    pdf_filename: str,
    dropbox_file_path: str,
    dropbox_shared_link: str,
    github_run_url: str,
):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    created_at = datetime.now(timezone.utc).isoformat()

    normalized = _extract_normalized_fields(fields)

    row = {
        "complaint_id": complaint_id,
        "submission_timestamp": submission_timestamp,
        "created_at_utc": created_at,
        "recipients": ",".join(recipients) if isinstance(recipients, list) else recipients,
        "customer_email": normalized["customer_email"],
        "country": normalized["country"],
        "product_name": normalized["product_name"],
        "lot_serial_no": normalized["lot_serial_no"],
        "complaint_type": normalized["complaint_type"],
        "pdf_filename": pdf_filename,
        "dropbox_file_path": dropbox_file_path,
        "dropbox_shared_link": dropbox_shared_link,
        "github_run_url": github_run_url,
        # Preserve everything (including mail_ok / mail_error)
        "all_fields_kv": json.dumps(fields, ensure_ascii=False),
    }

    file_exists = os.path.exists(CSV_PATH)

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)
