# Google Forms → PDF → Email (Always-Free Pipeline)

**Pipeline**
Google Form → Google Sheet → Apps Script (installable trigger) → GitHub `repository_dispatch` → GitHub Actions → Python generates PDF (ReportLab) → SMTP (SMTP2GO) sends email.

## Why this setup
- No always-on server.
- Low volume friendly.
- Uses an external trigger (`repository_dispatch`) to start a GitHub Actions run from Apps Script.
- SMTP2GO has a no-time-limit free plan suitable for ~10 emails/day (verify sender domain to avoid hourly throttling).

## 1) Google Form + linked Sheet
Create your Google Form and link responses to a Google Sheet (Responses tab → Link to Sheets).

## 2) Apps Script
1. In the linked Sheet: **Extensions → Apps Script**
2. Paste `apps_script/Code.gs`
3. Set Script Property **GITHUB_PAT** (Project settings → Script properties)
4. Add an installable trigger:
   - Triggers → Add Trigger
   - Function: `onFormSubmit`
   - Event source: From spreadsheet
   - Event type: On form submit

## 3) GitHub Secrets (Actions)
Repo → Settings → Secrets and variables → Actions → New repository secret:

- `SMTP_HOST` (e.g. `mail.smtp2go.com`)
- `SMTP_PORT` (`587`)
- `SMTP_USER`
- `SMTP_PASS`
- `MAIL_FROM` (must be verified with your SMTP provider)
- Optional: `MAIL_SUBJECT`, `MAIL_BODY`, `PDF_FILENAME`

> Important: `repository_dispatch` triggers only if the workflow file exists on the repo’s default branch.

## 4) SMTP2GO setup
- Create an SMTP2GO account
- Verify your sender domain/email
- Copy SMTP credentials into GitHub Secrets

## 5) Test
- Submit the Google Form once
- Check GitHub → Actions for a run
- Confirm the email arrives with a PDF attachment

## Local development
1. Copy `.env.example` → `.env` and fill values
2. Run:
   - Linux/macOS: `scripts/run_local.sh`
   - Windows: `scripts/run_local.bat`
