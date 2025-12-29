import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode
from dropbox.common import PathRoot


TEAM_NAMESPACE_ID = "1142808937"  # Redent Team Folder


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()

    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")

    if not folder:
        raise RuntimeError(
            "DROPBOX_FOLDER not set "
            "(example: /Customer Complaints/New CC procedure/00_inspection & repair report (Avi))"
        )

    if not folder.startswith("/"):
        folder = "/" + folder

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")
    print(f"[Dropbox] Using namespace_id={TEAM_NAMESPACE_ID}")

    # Create client
    dbx = dropbox.Dropbox(token)

    # IMPORTANT: route all calls to the TEAM FOLDER namespace
    dbx = dbx.with_path_root(
        PathRoot.namespace_id(TEAM_NAMESPACE_ID)
    )

    # Upload file
    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Try creating / fetching shared link
    shared_url = ""
    try:
        links = dbx.sharing_list_shared_links(
            path=target_path,
            direct_only=True
        ).links

        if links:
            shared_url = links[0].url
        else:
            shared_url = dbx.sharing_create_shared_link_with_settings(
                target_path
            ).url

        print(f"[Dropbox] Shared link: {shared_url}")

    except Exception as e:
        print(f"[Dropbox] Uploaded but shared link failed: {e}")

    return target_path, shared_url
