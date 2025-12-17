import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

CSV_PATH = "data/complaints_metadata.csv"

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


# For form label variations
ALIASES = {
    "customer_email": ["Email Address", "Email", "Customer Email", "E-mail", "Mail"],
    "country": ["Country"],
    "product_name": ["Product Name", "Product"],
    "lot_serial_no": ["LOT / Serial Number", "Lot / Serial Number", "LOT", "Serial Number", "Lot", "Serial"],
    "complaint_type": ["Complaint Type", "Type of Complaint"],
}


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x is not None)
    return str(v)


def _find_in_fields(fields: Dict[str, Any], labels: List[str]) -> str:
    """
    Find a value in fields dict by trying multiple label variants.
    """
    for k in labels:
        if k in fields and fields[k] not in (None, ""):
            return _to_str(fields[k]).strip()
    return ""


def _flatten_sections_to_map(sections: Any) -> Dict[str, str]:
    """
    sections format (from your debug output):
    [
      {"title": "...", "rows": [{"label": "...", "value": "..."}, ...]},
      ...
    ]
    """
    out: Dict[str, str] = {}
    if not sections:
        return out

    try:
        for sec in sections:
            rows = sec.get("rows", [])
            for r in rows:
                label = _to_str(r.get("label", "")).strip()
                value = _to_str(r.get("value", "")).strip()
                if label and value:
                    out[label] = value
    except Exception:
        # If structure differs, fail gracefully
        return out

    return out


def _extract_normalized(fields: Dict[str, Any], sections: Any) -> Dict[str, str]:
    flat = _flatten_sections_to_map(sections)

    def pick(col: str) -> str:
        labels = ALIASES[col]
        # Prefer fields dict, then sections map
        v = _find_in_fields(fields, labels)
        if v:
            return v
        for k in labels:
            if k in flat and flat[k]:
                return flat[k]
        return ""

    return {
        "customer_email": pick("customer_email"),
        "country": pick("country"),
        "product_name": pick("product_name"),
        "lot_serial_no": pick("lot_serial_no"),
        "complaint_type": pick("complaint_type"),
    }


def append_metadata_row(
    complaint_id: str,
    submission_timestamp: str,
    recipients,
    fields: Dict[str, Any],
    pdf_filename: str,
    dropbox_file_path: str,
    dropbox_shared_link: str,
    github_run_url: str,
    sections: Optional[Any] = None,  # <-- new, optional
):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    created_at = datetime.now(timezone.utc).isoformat()
    normalized = _extract_normalized(fields, sections)

    row = {
        "complaint_id": complaint_id,
        "submission_timestamp": _to_str(submission_timestamp),
        "created_at_utc": created_at,
        "recipients": _to_str(recipients),
        "customer_email": normalized["customer_email"],
        "country": normalized["country"],
        "product_name": normalized["product_name"],
        "lot_serial_no": normalized["lot_serial_no"],
        "complaint_type": normalized["complaint_type"],
        "pdf_filename": _to_str(pdf_filename),
        "dropbox_file_path": _to_str(dropbox_file_path),
        "dropbox_shared_link": _to_str(dropbox_shared_link),
        "github_run_url": _to_str(github_run_url),
        "all_fields_kv": json.dumps(
            {
                **fields,
                "_sections": sections,
            },
            ensure_ascii=False,
        ),
    }

    file_exists = os.path.exists(CSV_PATH)

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
