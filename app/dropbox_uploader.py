import os
from typing import Tuple

import dropbox
from dropbox.common import PathRoot
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode, FolderMetadata


def _normalize_folder(folder: str) -> str:
    folder = (folder or "").strip()
    if not folder:
        raise RuntimeError("DROPBOX_FOLDER not set (example: /CC_Test_Uploads)")
    if not folder.startswith("/"):
        folder = "/" + folder
    return folder.rstrip("/")  # keep as folder path, no trailing slash


def _get_dbx_with_correct_root(dbx: dropbox.Dropbox) -> dropbox.Dropbox:
    """
    If this user belongs to a Dropbox Business team, force all paths to be resolved
    against the Team Space (team root namespace). This is what makes your uploads
    land in the shared Team folder tree instead of personal space.

    Uses with_path_root() for compatibility with older SDKs (fixes path_root init error).
    """
    acct = dbx.users_get_current_account()
    root_info = getattr(acct, "root_info", None)

    if root_info and hasattr(root_info, "root_namespace_id"):
        ns_id = root_info.root_namespace_id
        print(f"[Dropbox] Detected team root namespace: {ns_id} -> using Team Space")
        return dbx.with_path_root(PathRoot.namespace_id(ns_id))

    print("[Dropbox] No team root detected -> using personal space")
    return dbx


def _ensure_folder(dbx: dropbox.Dropbox, folder: str) -> None:
    """
    Ensure Dropbox folder exists.
    """
    try:
        md = dbx.files_get_metadata(folder)
        if not isinstance(md, FolderMetadata):
            raise RuntimeError(f"DROPBOX_FOLDER exists but is not a folder: {folder}")
    except ApiError:
        # Folder missing -> create
        dbx.files_create_folder_v2(folder)
        print(f"[Dropbox] Created folder: {folder}")


def _get_or_create_shared_link(dbx: dropbox.Dropbox, target_path: str) -> str:
    """
    Create or reuse a shared link for the uploaded file.
    If the org restricts sharing or the scope isn't present, we just return "".
    """
    try:
        res = dbx.sharing_list_shared_links(path=target_path, direct_only=True)
        if res.links:
            return res.links[0].url

        return dbx.sharing_create_shared_link_with_settings(target_path).url
    except Exception as e:
        print(f"[Dropbox] Uploaded, but shared link not created: {e}")
        return ""


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Uploads a PDF to Dropbox and (optionally) returns a shared link.

    Required env:
      - DROPBOX_ACCESS_TOKEN
      - DROPBOX_FOLDER (Dropbox path, NOT Windows path)

    Suggested DROPBOX_FOLDER for your team folder:
      /Customer Complaints/New CC procedure/00_inspection & repair report (Avi)

    Returns:
      (target_path, shared_url)
    """
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")

    folder = _normalize_folder(folder)
    target_path = f"{folder}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    # Base client
    dbx = dropbox.Dropbox(token)

    # Validate token quickly
    try:
        dbx.users_get_current_account()
    except AuthError as e:
        raise RuntimeError(f"Dropbox auth failed (bad/expired token): {e}") from e

    # Force correct root (Team Space if available)
    dbx = _get_dbx_with_correct_root(dbx)

    # Ensure folder exists (in the correct root)
    _ensure_folder(dbx, folder)

    # Upload (overwrite helps testing + avoids collisions)
    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Shared link (optional)
    shared_url = _get_or_create_shared_link(dbx, target_path)
    if shared_url:
        print(f"[Dropbox] Shared link: {shared_url}")

    return target_path, shared_url
