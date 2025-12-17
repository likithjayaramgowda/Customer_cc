from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Submission:
    submission_id: str
    complaint_id: str
    timestamp: str
    form_title: str

    # status (kept, but no consent logic)
    status: str = "Received"

    # recipients
    email_to: List[str] = field(default_factory=list)

    # raw fields + dynamic sections
    fields: Dict[str, Any] = field(default_factory=dict)
    sections: List[Dict[str, Any]] = field(default_factory=list)


def load_event() -> Dict[str, Any]:
    """
    Loads the GitHub Actions event payload from GITHUB_EVENT_PATH.
    Works for repository_dispatch.
    """
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path or not os.path.exists(path):
        raise RuntimeError("GITHUB_EVENT_PATH is missing or file does not exist.")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _to_title_label(key: str) -> str:
    """
    Converts snake_case keys into readable labels for the PDF.
    Example: 'lot_serial_number' -> 'Lot Serial Number'
    """
    k = _safe_str(key).replace("__", " ").replace("_", " ").strip()
    if not k:
        return ""
    # Keep small words readable while still looking professional
    words = k.split()
    return " ".join(w[:1].upper() + w[1:] for w in words)


def _build_sections_from_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    If Apps Script didn't send explicit sections, we build one section dynamically
    from whatever fields exist. This is what makes the pipeline resilient to
    future Google Form question changes.

    We also skip technical keys.
    """
    if not isinstance(data, dict):
        return []

    skip_keys = {
        "submission_id",
        "complaint_id",
        "complaintid",
        "timestamp",
        "submission_timestamp",
        "form_title",
        "email_to",
        "sections",
    }

    rows = []
    for k, v in data.items():
        if k in skip_keys:
            continue

        vs = _safe_str(v)
        if vs == "":
            continue

        rows.append({"label": _to_title_label(k), "value": vs})

    if not rows:
        return []

    return [{"title": "Form Responses", "rows": rows}]


def parse_submission(event: Dict[str, Any]) -> Submission:
    """
    Parses GitHub repository_dispatch event into Submission.
    Expected shape:
      event["client_payload"] or event["client_payload"]["data"]
    """
    client_payload = event.get("client_payload") or {}
    if not isinstance(client_payload, dict):
        client_payload = {}

    # Some senders wrap everything inside client_payload.data
    data = client_payload.get("data")
    if isinstance(data, dict):
        merged_data = dict(data)
    else:
        merged_data = {}

    # Merge top-level fields too (so either format works)
    for k, v in client_payload.items():
        if k == "data":
            continue
        if k not in merged_data:
            merged_data[k] = v

    # IDs + timestamps
    submission_id = _safe_str(client_payload.get("submission_id") or merged_data.get("submission_id") or merged_data.get("complaint_id"))
    complaint_id = _safe_str(client_payload.get("complaint_id") or merged_data.get("complaint_id") or submission_id)
    timestamp = _safe_str(client_payload.get("submission_timestamp") or merged_data.get("submission_timestamp") or client_payload.get("timestamp") or merged_data.get("timestamp"))

    # Title
    form_title = _safe_str(client_payload.get("form_title") or merged_data.get("form_title") or "Customer Complaint Form")

    # Status
    status = _safe_str(os.environ.get("COMPLAINT_STATUS") or merged_data.get("status") or "Received")

    # Recipients (lab always)
    lab_email = os.environ.get("LAB_EMAIL", "lab@redentnova.de").strip()
    recipients = []
    if lab_email:
        recipients.append(lab_email)

    # Customer email (required now)
    customer_email = _safe_str(
        merged_data.get("email_address") or merged_data.get("email") or merged_data.get("email_address_2")
    )
    
    if customer_email and customer_email not in recipients:
        recipients.append(customer_email)


    # Sections: prefer explicitly provided sections, else build dynamically
    sections = client_payload.get("sections") or merged_data.get("sections")
    if isinstance(sections, list) and sections:
        final_sections = sections
    else:
        final_sections = _build_sections_from_data(merged_data)

    if not submission_id:
        # As a last resort, use complaint_id if present
        submission_id = complaint_id

    if not submission_id:
        raise ValueError("Missing submission_id/complaint_id in client_payload.")

    return Submission(
        submission_id=submission_id,
        complaint_id=complaint_id or submission_id,
        timestamp=timestamp,
        form_title=form_title,
        status=status,
        email_to=recipients,
        fields=merged_data,
        sections=final_sections,
    )
