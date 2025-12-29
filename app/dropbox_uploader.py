import os
from typing import Tuple, Optional

import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError
from dropbox.common import PathRoot


def _get_env(name: str, required: bool = False) -> str:
    val = os.environ.get(name, "").strip()
    if required and not val:
        raise RuntimeError(f"{name} not set")
    return val


def _normalize_dbx_path(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/")


def _dbx_personal(token: str) -> dropbox.Dropbox:
    return dropbox.Dropbox(token)


def _dbx_team_space(token: str, team_root_namespace_id: str) -> dropbox.Dropbox:
    """
    Creates a Dropbox client rooted at the Team Space namespace.
    NOTE: This does NOT grant permissions by itself. Your user must have access.
    """
    dbx = dropbox.Dropbox(token)
    # Root all paths to the team space namespace (so "/Customer Complaints/..." targets team space)
    return dbx.with_path_root(PathRoot.namespace_id(team_root_namespace_id))


def upload_pdf_to_dropbox(pdf_bytes: bytes, filename: str) -> Tuple[str, str]:
    """
    Option 2 workflow:
      1) Upload to PERSONAL staging folder
      2) Copy to TEAM folder (Team Space)
      3) Delete staging file if copy succeeds
    Returns: (final_path_or_staging_path, shared_link_if_created)
    """

    token = _get_env("DROPBOX_ACCESS_TOKEN", required=True)

    # Personal staging upload location (in your personal Dropbox)
    personal_folder = _normalize_dbx_path(_get_env("DROPBOX_PERSONAL_FOLDER", required=True))
    personal_path = f"{personal_folder}/{filename}"

    # Team destination location (Team Space path)
    team_folder = _normalize_dbx_path(_get_env("DROPBOX_TEAM_FOLDER", required=True))
    team_root_ns = _get_env("DROPBOX_TEAM_ROOT_NAMESPACE_ID", required=False)
    team_path = f"{team_folder}/{filename}"

    print(f"[Dropbox] Personal staging path: {personal_path}")
    print(f"[Dropbox] Team destination path:  {team_path}")

    dbx_personal = _dbx_personal(token)

    # 1) Upload into personal staging
    dbx_personal.files_upload(
        pdf_bytes,
        personal_path,
        mode=WriteMode.overwrite,
        mute=True,
    )
    print("[Dropbox] Uploaded to PERSONAL staging OK")

    # Create a share link for staging (so you always get something usable)
    staging_shared_url = ""
    try:
        links = dbx_personal.sharing_list_shared_links(path=personal_path, direct_only=True).links
        if links:
            staging_shared_url = links[0].url
        else:
            staging_shared_url = dbx_personal.sharing_create_shared_link_with_settings(personal_path).url
        print(f"[Dropbox] Staging shared link: {staging_shared_url}")
    except Exception as e:
        print(f"[Dropbox] Staging uploaded, but shared link not created: {e}")

    # If no team namespace provided, we cannot target Team Space reliably
    if not team_root_ns:
        print("[Dropbox] No DROPBOX_TEAM_ROOT_NAMESPACE_ID set. Skipping team copy.")
        return personal_path, staging_shared_url

    dbx_team = _dbx_team_space(token, team_root_ns)

    # 2) Try copy to team folder
    try:
        # Ensure destination folder exists (create_folder will fail if you don't have permissions)
        try:
            dbx_team.files_get_metadata(team_folder)
        except ApiError:
            dbx_team.files_create_folder_v2(team_folder)

        # Copy from personal -> team
        # Note: copy across namespaces generally works if you have access to the destination.
        dbx_team.files_copy_v2(from_path=personal_path, to_path=team_path, autorename=False)
        print("[Dropbox] Copied into TEAM folder OK")

        # 3) Delete staging file after successful copy
        try:
            dbx_personal.files_delete_v2(personal_path)
            print("[Dropbox] Deleted PERSONAL staging file OK")
        except Exception as e:
            print(f"[Dropbox] Team copy OK, but failed deleting staging file: {e}")

        # Create/reuse share link from TEAM location (optional)
        team_shared_url = ""
        try:
            links = dbx_team.sharing_list_shared_links(path=team_path, direct_only=True).links
            if links:
                team_shared_url = links[0].url
            else:
                team_shared_url = dbx_team.sharing_create_shared_link_with_settings(team_path).url
            print(f"[Dropbox] Team shared link: {team_shared_url}")
        except Exception as e:
            print(f"[Dropbox] Team copy OK, but shared link not created: {e}")

        return team_path, (team_shared_url or staging_shared_url)

    except Exception as e:
        print(f"[Dropbox] Team copy FAILED, keeping staging file. Reason: {e}")
        # Fallback: keep personal staging path/link
        return personal_path, staging_shared_url
