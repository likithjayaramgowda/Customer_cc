import os
from typing import Tuple, Optional

import dropbox
from dropbox.files import WriteMode, FolderMetadata
from dropbox.exceptions import ApiError, AuthError
from dropbox.common import PathRoot


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _ensure_folder(dbx: dropbox.Dropbox, folder: str) -> None:
    """
    Ensure folder exists. Creates it if missing.
    """
    try:
        md = dbx.files_get_metadata(folder)
        if isinstance(md, FolderMetadata):
            return
        raise RuntimeError(f"DROPBOX_FOLDER exists but is not a folder: {folder}")
    except ApiError:
        # Try to create
        dbx.files_create_folder_v2(folder)


def _build_client() -> dropbox.Dropbox:
    """
    Returns a Dropbox client that is correctly scoped for:
    - user tokens
    - team-scoped tokens (requires DROPBOX_TEAM_MEMBER_ID)
    - team folder namespace (optional but needed for Team Folders)
    """
    token = _env("DROPBOX_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")

    team_member_id = _env("DROPBOX_TEAM_MEMBER_ID")  # dbmid:xxxx
    team_ns_id = _env("DROPBOX_TEAM_FOLDER_NAMESPACE_ID")  # e.g. 1234567890 (digits)

    # First try as a normal user token
    dbx = dropbox.Dropbox(token)

    # If token is team-scoped, users_get_current_account can fail.
    # We detect and then switch to DropboxTeam + as_user(dbmid)
    try:
        dbx.users_get_current_account()
        # User token works
        if team_ns_id:
            dbx = dbx.with_path_root(PathRoot.namespace_id(team_ns_id))
        return dbx
    except Exception:
        # Likely a team-scoped token
        if not team_member_id:
            raise RuntimeError(
                "Team-scoped Dropbox token detected. Set DROPBOX_TEAM_MEMBER_ID (dbmid:...) "
                "to choose the target team member."
            )

        team = dropbox.DropboxTeam(token)

        # Act "as" a team member (this is the Select-User equivalent)
        dbx_user = team.as_user(team_member_id)

        # If uploading into a Team Folder, you usually need to set Path Root to that folder's namespace id
        if team_ns_id:
            dbx_user = dbx_user.with_path_root(PathRoot.namespace_id(team_ns_id))

        return dbx_user


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    folder = _env("DROPBOX_FOLDER")

    if not folder:
        raise RuntimeError(
            "DROPBOX_FOLDER not set (example: /Customer Complaints/New CC procedure/00_inspection & repair report (Avi))"
        )

    if not folder.startswith("/"):
        folder = "/" + folder

    dbx = _build_client()

    # Make sure folder exists in the current path root
    _ensure_folder(dbx, folder)

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    # Upload (overwrite = easy retests)
    dbx.files_upload(
        pdf_bytes,
        target_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Upload OK")

    # Shared link (optional)
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
