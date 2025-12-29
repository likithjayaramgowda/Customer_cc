import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError


def _ensure_folder(dbx: dropbox.Dropbox, folder: str) -> None:
    # Create folder if missing (safe for nested paths)
    try:
        dbx.files_get_metadata(folder)
        return
    except ApiError:
        dbx.files_create_folder_v2(folder)


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")
    if not folder:
        raise RuntimeError(
            "DROPBOX_FOLDER not set (example: /Redent Team Folder/Customer Complaints/New CC procedure/00_inspection & repair report (Avi))"
        )

    if not folder.startswith("/"):
        folder = "/" + folder

    dbx = dropbox.Dropbox(token)

    # Ensure target folder exists
    _ensure_folder(dbx, folder)

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Optional: shared link
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
