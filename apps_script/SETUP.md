# Google Forms → GitHub Actions Setup

This document explains how to connect the Google Form / Sheet to the GitHub Actions pipeline.

---

## 1. Where this script lives
- The Google Form is linked to a Google Sheet
- This script must be pasted into **Extensions → Apps Script** of that Sheet
- File name in Apps Script: `Code.gs`

Source of truth:
- `apps_script/Code.gs` in this repository

---

## 2. Required Script Properties
In Apps Script:
- Click **Project Settings**
- Add the following Script Properties:

| Key           | Value                                  |
|---------------|----------------------------------------|
| GITHUB_PAT    | GitHub Personal Access Token            |
| REPO_OWNER    | `raz-redentnova`                        |
| REPO_NAME     | `customer_complaint_form`               |

Notes:
- PAT must have `repo` scope
- No secrets are stored in the spreadsheet itself

---

## 3. Trigger setup (mandatory)
In Apps Script:
1. Click **Triggers** (clock icon)
2. Add Trigger:
   - Function: `onFormSubmit`
   - Event source: **From spreadsheet**
   - Event type: **On form submit**
3. Save and authorize

---

## 4. What the script does
- Normalizes headers dynamically (no hardcoded question mapping)
- Always includes the submitter email in the payload (email must be required in the form)
- Sends a unique submission id (GitHub generates the official Complaint ID)
- Writes initial status row to `Complaint_Status` sheet
- Sends payload to GitHub via `repository_dispatch`

---

## 5. Important design notes
- Form questions can be renamed, reordered, added, or removed
- PDF generation adapts automatically to form structure
- No code changes required for form edits
- Complaint ID and PDF filename are generated in GitHub Actions in the format `CCYYYY-NN`

---

## 6. Testing
- Submit a test response in the form
- Verify:
  - New GitHub Actions run is triggered
  - PDF is generated
  - Email is sent to `lab@redentnova.de`
  - Email is also sent to the customer email captured in the form

---

## 7. Common issues
- No GitHub run → check trigger exists
- 401/403 error → PAT missing or invalid
- PDF empty → form was submitted before trigger was installed

---

## 8. Migration note
Currently:
- Form and Sheet live in a personal Google account

Future:
- Script and logic are fully portable to RedentNova workspace
- Only requires re-pasting `Code.gs` and re-adding Script Properties
