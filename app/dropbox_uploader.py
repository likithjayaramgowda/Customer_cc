import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode, FolderMetadata
from dropbox.exceptions import ApiError


def _get_dropbox_client() -> dropbox.Dropbox:
    """
    Create a Dropbox client.
    Supports BOTH:
    - user-scoped tokens
    - team-scoped tokens (via DROPBOX_TEAM_MEMBER_ID)
    """
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    team_member_id = os.environ.get("DROPBOX_TEAM_MEMBER_ID", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")

    if team_member_id:
        # Team-scoped token → must select a user
        print(f"[Dropbox] Using team member context: {team_member_id}")
        return dropbox.Dropbox(
            oauth2_access_token=token,
            headers={
                "Dropbox-API-Select-User": team_member_id
            },
        )

    # User-scoped token
    print("[Dropbox] Using user-scoped token")
    return dropbox.Dropbox(oauth2_access_token=token)


def _ensure_folder_exists(dbx: dropbox.Dropbox, folder_path: str) -> None:
    """
    Ensure target folder exists. Create it if missing.
    """
    try:
        meta = dbx.files_get_metadata(folder_path)
        if isinstance(meta, FolderMetadata):
            return
        raise RuntimeError(f"Path exists but is not a folder: {folder_path}")
    except ApiError as e:
        # Folder does not exist → create it
        if e.error.is_path() and e.error.get_path().is_not_found():
            print(f"[Dropbox] Creating folder: {folder_path}")
            dbx.files_create_folder_v2(folder_path)
        else:
            raise


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Upload PDF to Dropbox and return:
    (dropbox_file_path, dropbox_shared_link)
    """
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()

    if not folder:
        raise RuntimeError("DROPBOX_FOLDER not set (example: /Customer Complaints/New CC procedure)")

    if not folder.startswith("/"):
        folder = "/" + folder

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    dbx = _get_dropbox_client()

    # Ensure folder exists
    _ensure_folder_exists(dbx, folder)

    # Upload file
    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Create or reuse shared link
    shared_url = ""
    try:
        links = dbx.sharing_list_shared_links(
            path=target_path,
            direct_only=True,
        ).links

        if links:
            shared_url = links[0].url
        else:
            shared_url = dbx.sharing_create_shared_link_with_settings(target_path).url

        print(f"[Dropbox] Shared link created")
    except Exception as e:
        print(f"[Dropbox] Uploaded, but shared link not created: {e}")

    return target_path, shared_url
