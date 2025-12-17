const INTERNAL_RECIPIENT = "lab@redentnova.de";

function onFormSubmit(e) {
  const form = FormApp.getActiveForm();
  const response = e.response;

  // Build sections dynamically from the form structure
  const sections = buildSections_(form, response);

  // Complaint metadata
  const complaintId = buildComplaintId_();
  const submissionTimestamp = new Date().toISOString();

  // Email must be REQUIRED in the form
  const customerEmail = extractEmail_(sections).trim();
  if (!customerEmail) {
    throw new Error("Customer email missing. Ensure the Email Address question is set to REQUIRED.");
  }

  // Always send to lab + submitter
  const emailTo = [INTERNAL_RECIPIENT, customerEmail];

  // Initial status record in linked response spreadsheet
  writeInitialStatus_(complaintId);

  // Dispatch to GitHub
  dispatchToGithub_({
    submission_id: complaintId,
    complaint_id: complaintId,
    submission_timestamp: submissionTimestamp,
    email_to: emailTo,
    sections: sections
  });
}


// ---------------------------
// Build sections + rows
// ---------------------------
function buildSections_(form, response) {
  const items = form.getItems();
  const itemMeta = {};
  let currentSectionTitle = "Form Details";

  for (const it of items) {
    const t = (it.getTitle() || "").trim();
    if (it.getType() === FormApp.ItemType.PAGE_BREAK) {
      currentSectionTitle = t || "Form Details";
      continue;
    }
    itemMeta[String(it.getId())] = { title: t || "Untitled Question", section: currentSectionTitle };
  }

  const sectionOrder = [];
  const sectionMap = {};

  const itemResponses = response.getItemResponses();
  for (const ir of itemResponses) {
    const item = ir.getItem();
    const id = String(item.getId());
    const meta = itemMeta[id] || { title: item.getTitle() || "Untitled Question", section: "Form Details" };

    let ans = ir.getResponse();
    let value = "";
    if (Array.isArray(ans)) value = ans.join(", ");
    else if (ans === null || ans === undefined) value = "";
    else value = String(ans);

    const sectionTitle = meta.section || "Form Details";
    if (!sectionMap[sectionTitle]) {
      sectionMap[sectionTitle] = [];
      sectionOrder.push(sectionTitle);
    }
    sectionMap[sectionTitle].push({ label: meta.title, value });
  }

  return sectionOrder.map(title => ({ title, rows: sectionMap[title] }));
}


// ---------------------------
// Extract email
// ---------------------------
function extractEmail_(sections) {
  for (const sec of sections) {
    for (const row of sec.rows) {
      const l = (row.label || "").toLowerCase();
      const v = (row.value || "").toString().trim();
      if (l.includes("email") && v.includes("@")) return v;
    }
  }
  return "";
}


// ---------------------------
// Status tracking (Sheet)
// ---------------------------
function writeInitialStatus_(complaintId) {
  const ssId = FormApp.getActiveForm().getDestinationId();
  if (!ssId) throw new Error("This Form is not linked to a response spreadsheet.");

  const ss = SpreadsheetApp.openById(ssId);
  const statusSheet = ss.getSheetByName("Complaint_Status");
  if (!statusSheet) throw new Error("Complaint_Status sheet not found in response spreadsheet.");

  const now = new Date().toISOString();
  statusSheet.appendRow([complaintId, now, "Received", now, ""]);
}


// ---------------------------
// GitHub dispatch
// ---------------------------
function dispatchToGithub_(clientPayload) {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty("GITHUB_PAT");
  const owner = props.getProperty("REPO_OWNER");
  const repo  = props.getProperty("REPO_NAME");
  if (!token || !owner || !repo) {
    throw new Error("Missing Script Properties: GITHUB_PAT, REPO_OWNER, REPO_NAME");
  }

  const url = `https://api.github.com/repos/${owner}/${repo}/dispatches`;
  const payload = { event_type: "complaint_submitted", client_payload: clientPayload };

  const res = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    headers: { Authorization: `token ${token}`, Accept: "application/vnd.github+json" },
    muteHttpExceptions: true
  });

  const code = res.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(`GitHub dispatch failed (${code}): ${res.getContentText()}`);
  }
}


// ---------------------------
// Complaint ID generator
// ---------------------------
function buildComplaintId_() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  return `RN-${y}${m}${d}-${hh}${mm}`;
}
