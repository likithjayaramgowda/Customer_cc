import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode, FolderMetadata
from dropbox.exceptions import ApiError


def _ensure_folder(dbx: dropbox.Dropbox, folder: str) -> None:
    try:
        md = dbx.files_get_metadata(folder)
        if isinstance(md, FolderMetadata):
            return
        raise RuntimeError(f"DROPBOX_FOLDER exists but is not a folder: {folder}")
    except ApiError as e:
        # Create folder if it doesn't exist
        try:
            dbx.files_create_folder_v2(folder)
            print(f"[Dropbox] Created folder: {folder}")
        except Exception as ce:
            raise RuntimeError(f"[Dropbox] Failed to create folder '{folder}': {ce}") from ce


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")
    if not folder:
        raise RuntimeError("DROPBOX_FOLDER not set (example: /CC_Test_Uploads)")

    if not folder.startswith("/"):
        folder = "/" + folder
    folder = folder.rstrip("/")

    dbx = dropbox.Dropbox(token)

    # Confirm token/account
    acct = dbx.users_get_current_account()
    print(f"[Dropbox] Auth OK as: {acct.email}")

    # Ensure folder exists
    _ensure_folder(dbx, folder)

    target_path = f"{folder}/{filename}"
    print(f"[Dropbox] Uploading to: {target_path}")

    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Verify it exists by listing folder
    try:
        entries = dbx.files_list_folder(folder).entries
        names = [e.name for e in entries]
        print(f"[Dropbox] Folder now contains: {names}")
    except Exception as e:
        print(f"[Dropbox] Could not list folder after upload: {e}")

    # Shared link
    shared_url = ""
    try:
        links = dbx.sharing_list_shared_links(path=target_path, direct_only=True).links
        if links:
            shared_url = links[0].url
        else:
            shared_url = dbx.sharing_create_shared_link_with_settings(target_path).url

        if shared_url and "dl=0" in shared_url:
            shared_url = shared_url.replace("dl=0", "dl=1")

        print(f"[Dropbox] Shared link: {shared_url}")
    except Exception as e:
        print(f"[Dropbox] Uploaded, but shared link not created: {e}")

    return target_path, shared_url
