from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


CSV_PATH = Path("data") / "complaints_metadata.csv"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(fields: Dict[str, Any], *keys: str) -> str:
    """Return the first non-empty field value for any of the given keys."""
    for k in keys:
        v = fields.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _flatten_kv(fields: Dict[str, Any]) -> str:
    """Stable, CSV-safe-ish representation for long term reference."""
    pairs: List[Tuple[str, str]] = []
    for k in sorted(fields.keys(), key=lambda x: str(x)):
        v = fields.get(k)
        if v is None:
            continue
        vs = str(v).strip()
        if vs == "":
            continue
        pairs.append((str(k), vs))

    # Use a compact format so it's easy to read in spreadsheets.
    # Example: key1=value1 | key2=value2
    return " | ".join([f"{k}={v}" for k, v in pairs])


CSV_COLUMNS = [
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


def append_metadata_row(
    *,
    complaint_id: str,
    submission_timestamp: str,
    recipients: List[str],
    fields: Dict[str, Any],
    pdf_filename: str,
    dropbox_file_path: str = "",
    dropbox_shared_link: str = "",
    github_run_url: str = "",
) -> None:
    """Append one complaint row to data/complaints_metadata.csv."""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "complaint_id": complaint_id,
        "submission_timestamp": submission_timestamp,
        "created_at_utc": _now_utc_iso(),
        "recipients": ", ".join([r.strip() for r in recipients if r and r.strip()]),
        "customer_email": _pick(fields, "email_address", "email", "email_address_2"),
        "country": _pick(fields, "country"),
        "product_name": _pick(fields, "product_name", "product"),
        "lot_serial_no": _pick(fields, "lot_serial_no", "lot_serial_number", "lot_serial"),
        "complaint_type": _pick(fields, "complaint_type", "type_of_complaint"),
        "pdf_filename": pdf_filename,
        "dropbox_file_path": dropbox_file_path,
        "dropbox_shared_link": dropbox_shared_link,
        "github_run_url": github_run_url,
        "all_fields_kv": _flatten_kv(fields),
    }

    def _ensure_header() -> None:
        if not CSV_PATH.exists():
            return

        try:
            with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                existing_header = next(reader, [])
        except Exception:
            existing_header = []

        if existing_header == CSV_COLUMNS:
            return

        # Migrate old CSV (best-effort): rewrite with new header and carry over known columns.
        rows_to_keep = []
        try:
            with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
                old = csv.DictReader(f)
                for r in old:
                    rows_to_keep.append(r)
        except Exception:
            rows_to_keep = []

        tmp = CSV_PATH.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            w.writeheader()
            for r in rows_to_keep:
                w.writerow({
                    "complaint_id": (r.get("complaint_id") or "").strip(),
                    "submission_timestamp": (r.get("submission_timestamp") or "").strip(),
                    "created_at_utc": (r.get("created_at_utc") or "").strip(),
                    "recipients": (r.get("recipients") or "").strip(),
                    "customer_email": (r.get("customer_email") or "").strip(),
                    "country": (r.get("country") or "").strip(),
                    "product_name": (r.get("product_name") or "").strip(),
                    "lot_serial_no": (r.get("lot_serial_no") or "").strip(),
                    "complaint_type": (r.get("complaint_type") or "").strip(),
                    "pdf_filename": (r.get("pdf_filename") or "").strip(),
                    "dropbox_file_path": (r.get("dropbox_file_path") or r.get("dropbox_folder") or "").strip(),
                    "dropbox_shared_link": (r.get("dropbox_shared_link") or "").strip(),
                    "github_run_url": (r.get("github_run_url") or "").strip(),
                    "all_fields_kv": (r.get("all_fields_kv") or "").strip(),
                })

        tmp.replace(CSV_PATH)

    _ensure_header()

    file_exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
