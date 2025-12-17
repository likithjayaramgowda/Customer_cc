import os
from typing import Tuple, Optional

import dropbox
from dropbox.files import WriteMode


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")
    if not folder:
        raise RuntimeError("DROPBOX_FOLDER not set (example: /CC_Test_Uploads)")

    if not folder.startswith("/"):
        folder = "/" + folder

    target_path = f"{folder.rstrip('/')}/{filename}"

    dbx = dropbox.Dropbox(token)

    print(f"[Dropbox] Uploading to: {target_path}")

    # Upload (overwrite to avoid conflicts during testing)
    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode("overwrite"),
        mute=True,
    )

    # Create or fetch shared link
    shared_url = ""
    try:
        links = dbx.sharing_list_shared_links(path=target_path, direct_only=True).links
        if links:
            shared_url = links[0].url
        else:
            shared_url = dbx.sharing_create_shared_link_with_settings(target_path).url
    except Exception as e:
        print(f"[Dropbox] Uploaded, but could not create shared link: {e}")

    print(f"[Dropbox] Upload OK: {target_path}")
    if shared_url:
        print(f"[Dropbox] Shared link: {shared_url}")

    return target_path, shared_url
