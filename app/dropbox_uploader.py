import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError


def _get_env(name: str) -> str:
    v = os.environ.get(name, "")
    return v.strip()


def _get_dropbox_client() -> dropbox.Dropbox:
    """
    Supports:
    1) Personal access token
    2) Dropbox Business team-scoped token (requires selecting a team member)
    """
    token = _get_env("DROPBOX_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")

    # Try personal-style client first
    dbx = dropbox.Dropbox(token)

    try:
        dbx.users_get_current_account()
        return dbx
    except Exception:
        # Likely a team-scoped token -> must select a team member
        team_member_id = _get_env("DROPBOX_TEAM_MEMBER_ID")
        if not team_member_id:
            raise RuntimeError(
                "Team-scoped Dropbox token detected. Set DROPBOX_TEAM_MEMBER_ID secret "
                "(example: dbmid:xxxxxxxxxxxxxx) to choose the target team member."
            )

        team = dropbox.DropboxTeam(token)
        return team.as_user(team_member_id)


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    folder = _get_env("DROPBOX_FOLDER")

    if not folder:
        raise RuntimeError("DROPBOX_FOLDER not set (example: /CC_Test_Uploads)")

    if not folder.startswith("/"):
        folder = "/" + folder

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    dbx = _get_dropbox_client()

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
    except ApiError as e:
        print(f"[Dropbox] Uploaded, but shared link not created: {e}")

    return target_path, shared_url
