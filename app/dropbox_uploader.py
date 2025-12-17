from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Tuple


DROPBOX_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"
DROPBOX_CREATE_LINK_URL = "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings"
DROPBOX_LIST_LINKS_URL = "https://api.dropboxapi.com/2/sharing/list_shared_links"
DROPBOX_OAUTH_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"


def _read_env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _truthy(val: str) -> bool:
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_dropbox_folder(folder: str) -> str:
    """
    Dropbox API paths must start with '/' and must use '/' separators.
    """
    folder = (folder or "").strip()
    folder = folder.replace("\\", "/")
    if not folder.startswith("/"):
        folder = "/" + folder
    return folder.rstrip("/")


def _sanitize_filename(filename: str) -> str:
    """
    Avoid path traversal and ensure the filename is a single path segment.
    """
    name = (filename or "complaint.pdf").strip()
    name = name.replace("\\", "_").replace("/", "_")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _dropbox_api_request_json(token: str, url: str, body: Dict) -> Dict:
    """
    Standard Dropbox JSON API request with good error messages.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Dropbox API error {e.code} {e.reason} at {url}: {detail}") from e


def _get_access_token() -> str:
    """
    Prefer refresh-token flow (stable). Fall back to DROPBOX_ACCESS_TOKEN if provided.
    """
    token = _read_env("DROPBOX_ACCESS_TOKEN")
    if token:
        return token

    app_key = _read_env("DROPBOX_APP_KEY")
    app_secret = _read_env("DROPBOX_APP_SECRET")
    refresh_token = _read_env("DROPBOX_REFRESH_TOKEN")

    if not (app_key and app_secret and refresh_token):
        raise RuntimeError(
            "Dropbox auth not configured. Provide either DROPBOX_ACCESS_TOKEN "
            "or DROPBOX_APP_KEY + DROPBOX_APP_SECRET + DROPBOX_REFRESH_TOKEN."
        )

    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": app_key,
            "client_secret": app_secret,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        DROPBOX_OAUTH_TOKEN_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Dropbox OAuth error {e.code} {e.reason}: {detail}") from e

    new_token = (payload.get("access_token") or "").strip()
    if not new_token:
        raise RuntimeError(f"Dropbox OAuth response missing access_token: {payload}")

    return new_token


def upload_pdf_to_dropbox(*, pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Uploads PDF to Dropbox and returns:
      (dropbox_file_path, shared_link_or_empty)

    Env vars supported:
      - Auth:
          DROPBOX_ACCESS_TOKEN
          OR DROPBOX_APP_KEY + DROPBOX_APP_SECRET + DROPBOX_REFRESH_TOKEN (recommended)
      - Folder:
          DROPBOX_FOLDER_PATH (preferred)
          DROPBOX_BASE_FOLDER (supported)
          DROPBOX_FOLDER_PATH (older naming)
      - Links:
          DROPBOX_CREATE_SHARED_LINK ("true"/"false", optional)
    """
    token = _get_access_token()

    folder = (
        _read_env("DROPBOX_FOLDER_PATH")
        or _read_env("DROPBOX_BASE_FOLDER")
        or _read_env("DROPBOX_FOLDER_PATH")
    )
    if not folder:
        raise RuntimeError("Dropbox folder not set. Use DROPBOX_FOLDER_PATH or DROPBOX_BASE_FOLDER.")

    folder = _normalize_dropbox_folder(folder)
    safe_name = _sanitize_filename(filename)
    dropbox_path = f"{folder}/{safe_name}"

    # ---- Upload ----
    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json.dumps(
            {
                "path": dropbox_path,
                "mode": "add",
                "autorename": True,
                "mute": False,
                "strict_conflict": False,
            }
        ),
    }

    req = urllib.request.Request(
        DROPBOX_UPLOAD_URL,
        data=pdf_bytes,
        method="POST",
        headers=upload_headers,
    )

    try:
        with urllib.request.urlopen(req) as resp:
            upload_result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Dropbox upload failed {e.code} {e.reason}: {detail}") from e

    final_path = (upload_result.get("path_display") or dropbox_path).strip()

    # ---- Shared link (optional) ----
    if not _truthy(_read_env("DROPBOX_CREATE_SHARED_LINK")):
        return final_path, ""

    # Create link (if exists, fallback to list)
    try:
        link_result = _dropbox_api_request_json(token, DROPBOX_CREATE_LINK_URL, {"path": final_path})
        return final_path, (link_result.get("url") or "").strip()
    except Exception:
        # list existing links
        try:
            list_result = _dropbox_api_request_json(
                token,
                DROPBOX_LIST_LINKS_URL,
                {"path": final_path, "direct_only": True},
            )
            links = list_result.get("links") or []
            if links:
                return final_path, (links[0].get("url") or "").strip()
        except Exception:
            pass

    return final_path, ""
