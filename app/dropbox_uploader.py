import os
from typing import Tuple

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
    print(f"[Dropbox] Target path: {target_path}")

    dbx = dropbox.Dropbox(token)

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
