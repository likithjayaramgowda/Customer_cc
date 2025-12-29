# app/dropbox_uploader.py

import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode, FolderMetadata
from dropbox.exceptions import ApiError


def _ensure_folder(dbx: dropbox.Dropbox, folder: str) -> None:
    """
    Ensure DROPBOX_FOLDER exists. Creates it if missing.
    For shared/team folders, this will work as long as the selected user has access.
    """
    try:
        md = dbx.files_get_metadata(folder)
        if isinstance(md, FolderMetadata):
            return
        raise RuntimeError(f"DROPBOX_FOLDER exists but is not a folder: {folder}")
    except ApiError:
        # Create folder if it doesn't exist
        try:
            dbx.files_create_folder_v2(folder)
            print(f"[Dropbox] Created folder: {folder}")
        except Exception as ce:
            raise RuntimeError(f"[Dropbox] Failed to create folder '{folder}': {ce}") from ce


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Upload PDF to Dropbox.

    Supports:
    - Regular user tokens
    - Team-scoped tokens by selecting a team member via:
        DROPBOX_TEAM_MEMBER_ID = "dbmid:xxxx..."
      (passed through Dropbox-API-Select-User header)

    Required env:
    - DROPBOX_ACCESS_TOKEN
    - DROPBOX_FOLDER   (example: /CC_Test_Uploads or /Customer Complaints/New CC procedure/00_inspection...)
    Optional env:
    - DROPBOX_TEAM_MEMBER_ID (dbmid:...)
    """
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()
    team_member_id = os.environ.get("DROPBOX_TEAM_MEMBER_ID", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")
    if not folder:
        raise RuntimeError("DROPBOX_FOLDER not set (example: /CC_Test_Uploads)")

    if not folder.startswith("/"):
        folder = "/" + folder

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    # If team-scoped token, select a member explicitly
    if team_member_id:
        print(f"[Dropbox] Using team member: {team_member_id}")
        dbx = dropbox.Dropbox(
            oauth2_access_token=token,
            headers={"Dropbox-API-Select-User": team_member_id},
        )
    else:
        dbx = dropbox.Dropbox(oauth2_access_token=token)

    # Optional: ensure the folder exists (safe; if folder is a shared/team folder, user must have access)
    _ensure_folder(dbx, folder)

    # Upload (overwrite avoids name conflicts during testing)
    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Create or reuse a shared link (optional)
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
