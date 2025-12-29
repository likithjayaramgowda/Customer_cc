import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode, FolderMetadata
from dropbox.exceptions import ApiError
from dropbox.common import PathRoot


def _get_team_root_namespace_id(dbx: dropbox.Dropbox) -> str:
    """
    If this Dropbox account is a Business account with Team Space,
    this returns the team 'root_namespace_id'. If not available, returns "".
    """
    try:
        acct = dbx.users_get_current_account()
        root_info = getattr(acct, "root_info", None)
        if root_info and hasattr(root_info, "root_namespace_id"):
            return root_info.root_namespace_id
    except Exception:
        pass
    return ""


def _ensure_folder(dbx: dropbox.Dropbox, folder_path: str) -> None:
    try:
        md = dbx.files_get_metadata(folder_path)
        if isinstance(md, FolderMetadata):
            return
        raise RuntimeError(f"DROPBOX_FOLDER exists but is not a folder: {folder_path}")
    except ApiError:
        # Create if it doesn't exist
        dbx.files_create_folder_v2(folder_path)


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")
    if not folder:
        raise RuntimeError("DROPBOX_FOLDER not set (example: /Customer Complaints/New CC procedure/00_inspection & repair report (Avi))")

    if not folder.startswith("/"):
        folder = "/" + folder

    # Base client (home namespace by default)
    dbx = dropbox.Dropbox(token)

    # If this is a Business account with Team Space, switch Path Root to team root
    team_root_ns = _get_team_root_namespace_id(dbx)
    if team_root_ns:
        print(f"[Dropbox] Detected team root namespace: {team_root_ns} -> using Team Space")
        dbx = dropbox.Dropbox(token, path_root=PathRoot.namespace_id(team_root_ns))
    else:
        print("[Dropbox] No team root namespace detected -> using personal space")

    # Ensure folder exists in the ACTIVE namespace (team or personal depending above)
    _ensure_folder(dbx, folder)

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    # Upload
    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Optional shared link
    shared_url = ""
    try:
        links = dbx.sharing_list_shared_links(path=target_path, direct_only=True).links
        if links:
            shared_url = links[0].url
        else:
            shared_url = dbx.sharing_create_shared_link_with_settings(target_path).url
        print(f"[Dropbox] Shared link: {shared_url}")
    except Exception as e:
        print(f"[Dropbox] Uploaded, but shared link not created: {e}")

    return target_path, shared_url
