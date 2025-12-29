# app/dropbox_uploader.py

import os
from typing import Tuple

import dropbox
from dropbox.files import WriteMode, FolderMetadata
from dropbox.exceptions import ApiError


def _is_team_scoped_token_error(err: Exception) -> bool:
    """
    Detects the common Dropbox Business error when a team-scoped token is used
    without selecting a specific team member (Dropbox-API-Select-User).
    """
    msg = str(err).lower()
    return (
        "oauth 2 access token you provided is for an entire dropbox business team" in msg
        or "dropbox-api-select-user" in msg
        or "select_user" in msg
        or "team-scoped" in msg
    )


def _get_dropbox_client() -> dropbox.Dropbox:
    """
    Creates a Dropbox client.
    - If DROPBOX_TEAM_MEMBER_ID is set, we attach Dropbox-API-Select-User header,
      which is REQUIRED for team-scoped tokens (Dropbox Business).
    - Otherwise, uses a normal user-scoped client.
    """
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DROPBOX_ACCESS_TOKEN not set")

    team_member_id = os.environ.get("DROPBOX_TEAM_MEMBER_ID", "").strip()

    if team_member_id:
        # Team-scoped token: must select a user context for file endpoints
        print(f"[Dropbox] Using team-scoped token with Select-User: {team_member_id}")
        return dropbox.Dropbox(
            oauth2_access_token=token,
            headers={"Dropbox-API-Select-User": team_member_id},
        )

    print("[Dropbox] Using user-scoped token")
    return dropbox.Dropbox(oauth2_access_token=token)


def _ensure_folder(dbx: dropbox.Dropbox, folder: str) -> None:
    """
    Ensures the target folder exists (creates it if missing).
    Works in the selected user context.
    """
    try:
        md = dbx.files_get_metadata(folder)
        if isinstance(md, FolderMetadata):
            return
        raise RuntimeError(f"DROPBOX_FOLDER exists but is not a folder: {folder}")
    except ApiError as e:
        # Create folder if not found
        try:
            dbx.files_create_folder_v2(folder)
            print(f"[Dropbox] Created folder: {folder}")
        except Exception as ce:
            raise RuntimeError(f"[Dropbox] Failed to create folder '{folder}': {ce}") from ce


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Uploads PDF bytes to Dropbox and returns:
      (dropbox_file_path, dropbox_shared_link)

    Env vars:
      - DROPBOX_ACCESS_TOKEN (required)
      - DROPBOX_FOLDER (required) e.g.:
          /Customer Complaints/New CC procedure/00_inspection & repair report (Avi)
        or for personal testing:
          /CC_Test_Uploads
      - DROPBOX_TEAM_MEMBER_ID (required ONLY for team-scoped tokens) e.g.:
          dbmid:xxxxxxxxxxxxxxxxxxxx
    """
    folder = os.environ.get("DROPBOX_FOLDER", "").strip()
    if not folder:
        raise RuntimeError(
            "DROPBOX_FOLDER not set (example: /CC_Test_Uploads or "
            "/Customer Complaints/New CC procedure/00_inspection & repair report (Avi))"
        )

    if not folder.startswith("/"):
        folder = "/" + folder

    target_path = f"{folder.rstrip('/')}/{filename}"
    print(f"[Dropbox] Target path: {target_path}")

    dbx = _get_dropbox_client()

    # Ensure folder exists
    _ensure_folder(dbx, folder)

    # Upload (overwrite avoids conflicts during testing)
    try:
        dbx.files_upload(
            pdf_bytes,
            target_path,
            mode=WriteMode.overwrite,
            mute=True,
        )
        print("[Dropbox] Upload OK")
    except Exception as e:
        # Provide a very explicit hint if this is the team-scoped select-user issue
        if _is_team_scoped_token_error(e):
            raise RuntimeError(
                "Team-scoped Dropbox token detected. You MUST set DROPBOX_TEAM_MEMBER_ID "
                "(example: dbmid:xxxxxxxxxxxx) so uploads run in a team member context."
            ) from e
        raise

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
