from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


CSV_PATH = Path("data") / "complaints_metadata.csv"


_ID_RE = re.compile(r"^CC(?P<year>\d{4})-(?P<num>\d{2})$")


def _year_from_timestamp(ts: str) -> int:
    ts = (ts or "").strip()
    if ts:
        # ISO8601 variants (e.g. 2025-12-17T09:00:00Z)
        try:
            t2 = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(t2).year
        except Exception:
            pass

        # Common human timestamps (best-effort)
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%d/%m/%Y",
        ):
            try:
                return datetime.strptime(ts, fmt).year
            except Exception:
                continue

    return datetime.now(timezone.utc).year


def _max_seq_for_year(year: int) -> int:
    if not CSV_PATH.exists():
        return 0

    max_n = 0
    try:
        with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = (row.get("complaint_id") or "").strip()
                m = _ID_RE.match(cid)
                if not m:
                    continue
                if int(m.group("year")) != year:
                    continue
                n = int(m.group("num"))
                if n > max_n:
                    max_n = n
    except Exception:
        # If the CSV is temporarily malformed, fail safe by restarting the counter.
        return 0

    return max_n


def next_complaint_id(submission_timestamp: str) -> str:
    """Generate complaint id in the format CCYYYY-NN (NN starts at 01 each year)."""
    year = _year_from_timestamp(submission_timestamp)
    next_n = _max_seq_for_year(year) + 1
    if next_n > 99:
        # If you ever exceed 99 per year, bump format later.
        raise RuntimeError(f"Complaint sequence exceeded 99 for year {year}.")
    return f"CC{year}-{next_n:02d}"
