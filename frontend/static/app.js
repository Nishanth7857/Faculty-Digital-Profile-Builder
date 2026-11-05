/**
 * app.js  –  Smart Faculty Profile Agent frontend logic
 * ────────────────────────────────────────────────────────────────────────────
 * All communication with the FastAPI backend happens via fetch() calls.
 * No external libraries – plain vanilla JS so any student can read it.
 */

// Keeps track of files the user has selected before uploading
let selectedFiles = [];

// Stores the current profile JSON for the edit form
let currentProfile = {};

// ─────────────────────────────────────────────────────────────────────────────
// Tab navigation
// ─────────────────────────────────────────────────────────────────────────────

/**
 * showTab(tabId) – hide all tabs, show the requested one.
 * Also marks the matching sidebar button as active.
 */
function showTab(tabId) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".step-btn").forEach(b => b.classList.remove("active"));

  document.getElementById(tabId).classList.add("active");

  // Map tabId → step button index (0-based)
  const tabOrder = ["tab-upload", "tab-extract", "tab-edit", "tab-generate", "tab-export"];
  const idx = tabOrder.indexOf(tabId);
  const btns = document.querySelectorAll(".step-btn");
  if (btns[idx]) btns[idx].classList.add("active");

  // Refresh stats whenever the user navigates
  loadStats();
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast notifications
// ─────────────────────────────────────────────────────────────────────────────

/**
 * showToast(msg, type) – display a brief notification at the bottom-right.
 * type: "default" | "success" | "error"
 */
function showToast(msg, type = "default") {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3500);
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 1 – File upload
// ─────────────────────────────────────────────────────────────────────────────

// Drag-and-drop support on the drop zone
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");

dropZone.addEventListener("dragover", e => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  handleFilesSelected(Array.from(e.dataTransfer.files));
});

dropZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  handleFilesSelected(Array.from(fileInput.files));
  fileInput.value = "";  // reset so the same file can be re-added
});

/**
 * handleFilesSelected(files) – add newly selected files to the staging list.
 */
function handleFilesSelected(files) {
  files.forEach(f => {
    if (!selectedFiles.find(sf => sf.name === f.name)) {
      selectedFiles.push(f);
    }
  });
  renderFileList();
  document.getElementById("upload-btn").disabled = selectedFiles.length === 0;
}

/**
 * renderFileList() – re-render the chip list of staged files.
 */
function renderFileList() {
  const container = document.getElementById("file-list");
  container.innerHTML = "";
  selectedFiles.forEach((f, i) => {
    const chip = document.createElement("div");
    chip.className = "file-chip";
    chip.innerHTML = `
      <span>${fileIcon(f.name)}</span>
      <span>${f.name}</span>
      <span style="font-size:11px;color:#8b949e;">(${formatBytes(f.size)})</span>
      <button onclick="removeFile(${i})" title="Remove">✕</button>
    `;
    container.appendChild(chip);
  });
}

function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderFileList();
  document.getElementById("upload-btn").disabled = selectedFiles.length === 0;
}

function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  const icons = { pdf: "📄", docx: "📝", doc: "📝", xlsx: "📊", xls: "📊", csv: "📊",
                  png: "🖼", jpg: "🖼", jpeg: "🖼", tiff: "🖼" };
  return icons[ext] || "📎";
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

/**
 * uploadFiles() – POST all staged files to /api/upload.
 */
async function uploadFiles() {
  if (selectedFiles.length === 0) return;

  const btn = document.getElementById("upload-btn");
  const resultBox = document.getElementById("upload-result");
  btn.disabled = true;
  btn.textContent = "Uploading…";
  resultBox.classList.add("hidden");

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append("files", f));

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      showResult(resultBox, "error", data.detail || "Upload failed.");
      showToast("Upload failed", "error");
    } else {
      // Build a success summary
      const lines = data.results.map(r =>
        r.status === "ok"
          ? `✔ ${r.file} — ${r.chars_extracted} chars, ${r.chunks_added} chunks ingested`
          : `✗ ${r.file} — ${r.detail}`
      ).join("\n");
      showResult(resultBox, "success", `${data.message}\n\n${lines}`);
      showToast("Files uploaded successfully!", "success");
      selectedFiles = [];
      renderFileList();
      loadStats();
    }
  } catch (err) {
    showResult(resultBox, "error", "Network error: " + err.message);
    showToast("Network error", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Upload & Ingest";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 2 – Extract profile data
// ─────────────────────────────────────────────────────────────────────────────

/**
 * extractProfile() – POST to /api/extract and display the structured JSON.
 */
async function extractProfile() {
  const spinner = document.getElementById("extract-spinner");
  const output = document.getElementById("extract-output");
  const badge = document.getElementById("extract-token-badge");

  spinner.textContent = "Running Granite extraction (RAG + LLM)… please wait";
  spinner.classList.remove("hidden");
  output.classList.add("hidden");
  badge.classList.add("hidden");

  try {
    const res = await fetch("/api/extract", { method: "POST" });
    const data = await res.json();
    spinner.classList.add("hidden");

    if (!res.ok) {
      showToast(data.detail || "Extraction failed", "error");
      output.textContent = JSON.stringify(data, null, 2);
      output.classList.remove("hidden");
      return;
    }

    currentProfile = data.profile;
    output.textContent = JSON.stringify(data.profile, null, 2);
    output.classList.remove("hidden");

    // Show token badge
    const tok = data.token_usage;
    badge.textContent = `Tokens used — Input: ${tok.input_tokens}  |  Output: ${tok.output_tokens}`;
    badge.classList.remove("hidden");

    showToast("Extraction complete!", "success");
    loadStats();
    // Pre-populate the edit form
    buildEditForm(currentProfile);
  } catch (err) {
    spinner.classList.add("hidden");
    showToast("Error: " + err.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 3 – Edit form
// ─────────────────────────────────────────────────────────────────────────────

/**
 * buildEditForm(profile) – dynamically render editable fields from the profile.
 * Personal details get individual inputs; list sections get JSON textareas.
 */
function buildEditForm(profile) {
  const form = document.getElementById("edit-form");
  form.innerHTML = "";

  if (!profile || Object.keys(profile).length === 0) {
    form.innerHTML = "<p class='muted-text'>No profile data yet. Run extraction first.</p>";
    return;
  }

  // Personal details – individual fields
  const personal = profile.personal_details || {};
  const personalSection = section("Personal Details");
  form.appendChild(personalSection);

  const personalFields = ["name", "designation", "department", "institution", "email", "phone", "date_of_birth"];
  personalFields.forEach(key => {
    personalSection.appendChild(inputField(key, personal[key] || "", `personal__${key}`));
  });

  // List sections – JSON textarea editors
  const listSections = [
    { key: "qualifications",      label: "Academic Qualifications" },
    { key: "publications",        label: "Publications" },
    { key: "fdp_workshops",       label: "FDPs & Workshops" },
    { key: "patents",             label: "Patents" },
    { key: "grants_projects",     label: "Grants & Projects" },
    { key: "achievements_awards", label: "Achievements & Awards" },
  ];

  listSections.forEach(({ key, label }) => {
    const sec = section(label);
    form.appendChild(sec);
    const wrap = document.createElement("div");
    wrap.className = "list-editor";
    const ta = document.createElement("textarea");
    ta.id = `list__${key}`;
    ta.value = JSON.stringify(profile[key] || [], null, 2);
    ta.placeholder = `Edit ${label} as JSON array…`;
    wrap.appendChild(ta);
    sec.appendChild(wrap);
  });
}

function section(title) {
  const div = document.createElement("div");
  const h = document.createElement("div");
  h.className = "edit-section-title";
  h.textContent = title;
  div.appendChild(h);
  return div;
}

function inputField(key, value, id) {
  const row = document.createElement("div");
  row.className = "edit-field";
  row.innerHTML = `
    <label for="${id}">${key.replace(/_/g, " ")}</label>
    <input id="${id}" type="text" value="${escapeHtml(String(value || ""))}" />
  `;
  return row;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/**
 * saveEdits() – read all form values and PUT to /api/profile/edit.
 */
async function saveEdits() {
  const corrections = { personal_details: {} };

  // Read personal detail inputs
  ["name", "designation", "department", "institution", "email", "phone", "date_of_birth"].forEach(key => {
    const el = document.getElementById(`personal__${key}`);
    if (el) corrections.personal_details[key] = el.value;
  });

  // Read list sections
  const listKeys = ["qualifications", "publications", "fdp_workshops", "patents", "grants_projects", "achievements_awards"];
  listKeys.forEach(key => {
    const el = document.getElementById(`list__${key}`);
    if (el) {
      try {
        corrections[key] = JSON.parse(el.value);
      } catch (e) {
        showToast(`Invalid JSON in "${key}" — please fix before saving.`, "error");
        throw e;
      }
    }
  });

  const resultBox = document.getElementById("edit-result");
  try {
    const res = await fetch("/api/profile/edit", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corrections }),
    });
    const data = await res.json();

    if (!res.ok) {
      showResult(resultBox, "error", data.detail);
      showToast("Save failed", "error");
    } else {
      currentProfile = data.profile;
      showResult(resultBox, "success", "Corrections saved successfully.");
      showToast("Changes saved!", "success");
    }
  } catch (err) {
    // JSON parse errors from above are already toasted
  }
}

/**
 * mergeProfile() – ask Granite to clean up / deduplicate the stored profile.
 */
async function mergeProfile() {
  const resultBox = document.getElementById("edit-result");
  showResult(resultBox, "success", "Sending profile to Granite for merge…");
  try {
    const res = await fetch("/api/profile/merge", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showResult(resultBox, "error", data.detail);
      showToast("Merge failed", "error");
    } else {
      currentProfile = data.profile;
      buildEditForm(currentProfile);
      showResult(resultBox, "success", "Granite merge complete. Form refreshed.");
      showToast("Profile merged!", "success");
      loadStats();
    }
  } catch (err) {
    showResult(resultBox, "error", err.message);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Step 4 – Generate profile text + bio
// ─────────────────────────────────────────────────────────────────────────────

/**
 * generateProfile() – POST to /api/generate and display the narrative texts.
 */
async function generateProfile() {
  const spinner = document.getElementById("generate-spinner");
  const output  = document.getElementById("generate-output");
  const badge   = document.getElementById("generate-token-badge");

  spinner.textContent = "Granite is writing the profile and bio… please wait";
  spinner.classList.remove("hidden");
  output.classList.add("hidden");
  badge.classList.add("hidden");

  try {
    const res = await fetch("/api/generate", { method: "POST" });
    const data = await res.json();
    spinner.classList.add("hidden");

    if (!res.ok) {
      showToast(data.detail || "Generation failed", "error");
      return;
    }

    document.getElementById("bio-text").textContent = data.bio;
    document.getElementById("full-profile-text").textContent = data.full_profile;
    output.classList.remove("hidden");

    const tok = data.token_usage;
    badge.textContent = `Tokens used — Input: ${tok.input_tokens}  |  Output: ${tok.output_tokens}`;
    badge.classList.remove("hidden");

    showToast("Profile text generated!", "success");
    loadStats();
  } catch (err) {
    spinner.classList.add("hidden");
    showToast("Error: " + err.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Stats dashboard
// ─────────────────────────────────────────────────────────────────────────────

/**
 * loadStats() – GET /api/stats and refresh the sidebar token counters.
 */
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const data = await res.json();
    const u = data.token_usage;

    setText("stat-files", data.file_count);
    setText("stat-ext-in",  u.extract_input  || 0);
    setText("stat-ext-out", u.extract_output || 0);
    setText("stat-gen-in",  u.generate_input  || 0);
    setText("stat-gen-out", u.generate_output || 0);
    setText("stat-ref",     (u.refine_input || 0) + (u.refine_output || 0));
    setText("stat-emb",     u.embed_tokens   || 0);
    setText("stat-total",   data.total_tokens);
  } catch (_) {
    // Silently ignore stats errors (backend may still be starting)
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Reset
// ─────────────────────────────────────────────────────────────────────────────

/**
 * resetAll() – DELETE /api/reset after a confirmation dialog.
 */
async function resetAll() {
  if (!confirm("Are you sure you want to delete ALL data? This cannot be undone.")) return;
  try {
    const res = await fetch("/api/reset", { method: "DELETE" });
    const data = await res.json();
    showToast(data.message, "success");
    currentProfile = {};
    document.getElementById("edit-form").innerHTML =
      "<p class='muted-text'>Run extraction first (Step 2) to see editable fields here.</p>";
    document.getElementById("extract-output").classList.add("hidden");
    document.getElementById("generate-output").classList.add("hidden");
    selectedFiles = [];
    renderFileList();
    loadStats();
  } catch (err) {
    showToast("Reset failed: " + err.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Utility helpers
// ─────────────────────────────────────────────────────────────────────────────

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function showResult(box, type, msg) {
  box.className = `result-box ${type}`;
  box.style.whiteSpace = "pre-wrap";
  box.textContent = msg;
  box.classList.remove("hidden");
}

// ─────────────────────────────────────────────────────────────────────────────
// Init – load stats on page load
// ─────────────────────────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  loadStats();
  // If a profile already exists, pre-populate the edit form
  fetch("/api/profile").then(r => r.ok ? r.json() : null).then(data => {
    if (data && data.profile) {
      currentProfile = data.profile;
      buildEditForm(currentProfile);
    }
  }).catch(() => {});
});
