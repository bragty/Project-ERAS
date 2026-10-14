let patients = [];
let showArchived = false;
let searchTimer = null;

function esc(value){
  return String(value == null ? "" : value).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function checklistUrl(patient){
  const base = document.querySelector("[data-checklist-url]").dataset.checklistUrl;
  const params = new URLSearchParams();
  params.set("patient", patient.name || "");
  params.set("case", patient.caseNumber || "");
  params.set("opdate", patient.opDate || "");
  return `${base}?${params.toString()}`;
}

async function goToChecklist(patient){
  try {
    // Resolve the selected case through the backend before navigation. This
    // prevents stale browser-only patient data from being used.
    const payload = await window.erasApi.fetch(`/api/cases/${encodeURIComponent(patient.caseNumber)}/`);
    window.location.href = checklistUrl(payload.case);
  } catch (err) {
    alert(err.message || "Fall konnte nicht geöffnet werden.");
  }
}

function patientRowHTML(patient){
  return `
    <div class="patient-row clickable" data-case-number="${esc(patient.caseNumber)}" tabindex="0" role="link" aria-label="Checkliste für ${esc(patient.name || "Patient")} öffnen">
      <div><strong>${esc(patient.name || "-")}</strong><small>${esc(patient.patientNumber || "")}</small></div>
      <div>${esc(patient.caseNumber || "-")}</div>
      <div>${esc(patient.opDate || "offen")}</div>
      <div>${esc(patient.procedure || "-")}</div>
      <div class="progress-cell">
        <div class="progress-track"><div class="progress-fill" style="width:${Number(patient.progress || 0)}%"></div></div>
        <span class="progress-value">${Number(patient.progress || 0)}%</span>
        <button
  class="btn archive-icon"
  data-archive-case="${esc(patient.caseNumber)}"
  aria-label="${patient.archived ? 'Wiederherstellen' : 'Archivieren'}"
  title="${!patient.archived && !patient.complete
    ? 'Alle Checklistenpunkte müssen abgeschlossen sein'
    : patient.archived ? 'Wiederherstellen' : 'Archivieren'}"
  ${!patient.archived && !patient.complete ? 'disabled' : ''}>
  <span aria-hidden="true">${patient.archived ? '↶' : '▣'}</span>
</button>
      </div>
    </div>
  `;
}

function updatePreview(patient){
  document.getElementById("previewName").textContent = patient && patient.name ? patient.name : "-";
  document.getElementById("previewCase").textContent = patient && patient.caseNumber ? patient.caseNumber : "-";
  document.getElementById("previewOpDate").textContent = patient && patient.opDate ? patient.opDate : "-";
  document.getElementById("previewProcedure").textContent = patient && patient.procedure ? patient.procedure : "-";
}

function tableHeaderHTML(){
  return `
    <div class="patient-row header">
      <div>Patient*in</div>
      <div>Fallnummer</div>
      <div>OP Datum</div>
      <div>Eingriffsart</div>
      <div>Progression</div>
    </div>
  `;
}

function renderSearchResults(){
  const results = document.getElementById("patientSearchResults");
  const query = document.getElementById("patientSearch").value.trim();
  const label = query ? `${patients.length} Treffer` : (showArchived ? "Archivierte Fälle" : "Aktive Fälle");
  results.innerHTML = `
    <div class="search-results-head">${esc(label)}</div>
    <div class="patient-table search-table">
      ${tableHeaderHTML()}
      ${patients.length ? patients.map(patientRowHTML).join("") : `<div class="empty-results">Keine passenden Patientinnen oder Patienten gefunden.</div>`}
    </div>
  `;
}

async function loadPatients(options){
  const background = !!(options && options.background);
  const results = document.getElementById("patientSearchResults");
  const query = document.getElementById("patientSearch").value.trim();
  try {
    const params = new URLSearchParams({ archived: String(showArchived) });
    if (query) params.set("q", query);
    const payload = await window.erasApi.fetch(`/api/patients/?${params.toString()}`);
    // A background refresh must not overwrite results of a newer search.
    if (background && query !== document.getElementById("patientSearch").value.trim()) return;
    const next = payload.results || [];
    // Re-render only on changes, so focus/hover in the table is not disturbed.
    if (background && JSON.stringify(next) === JSON.stringify(patients)) return;
    patients = next;
    renderSearchResults();
  } catch (err) {
    if (background) return;
    patients = [];
    results.innerHTML = `<div class="empty-results">${esc(err.message || "Patienten konnten nicht geladen werden.")}</div>`;
  }
}

// Keeps the overview current while other workstations edit cases.
const PATIENT_POLL_MS = 5000;
let patientPollBusy = false;
async function pollPatients(){
  if (patientPollBusy || document.hidden || searchTimer) return;
  patientPollBusy = true;
  try { await loadPatients({ background: true }); } finally { patientPollBusy = false; }
}

function openModal(){
  const modal = document.getElementById("patientModal");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.getElementById("newPatientName").focus();
}

function closeModal(){
  const modal = document.getElementById("patientModal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function clearModal(){
  ["newBeneNurse","newBeneDeputy","newSurgeon","newPatientName","newPatientNumber","newCaseNumber","newOpDate","newProcedure"].forEach(id => {
    document.getElementById(id).value = "";
  });
}

async function savePatient(){
  const patient = {
    beneNurse: document.getElementById("newBeneNurse").value.trim(),
    beneDeputy: document.getElementById("newBeneDeputy").value.trim(),
    surgeon: document.getElementById("newSurgeon").value.trim(),
    name: document.getElementById("newPatientName").value.trim(),
    patientNumber: document.getElementById("newPatientNumber").value.trim(),
    caseNumber: document.getElementById("newCaseNumber").value.trim(),
    opDate: document.getElementById("newOpDate").value,
    procedure: document.getElementById("newProcedure").value
  };
  if(!patient.name || !patient.caseNumber){alert("Name und eindeutige Fallnummer sind erforderlich.");return;}
  try {
    const payload = await window.erasApi.fetch("/api/patients/", {
      method: "POST",
      body: JSON.stringify(patient)
    });
    document.getElementById("patientSearch").value = payload.case.caseNumber;
    updatePreview(payload.case);
    clearModal();
    closeModal();
    await loadPatients();
  } catch (err) {
    alert(err.message || "Patient konnte nicht gespeichert werden.");
  }
}

function findCase(caseNumber){
  return patients.find(patient => patient.caseNumber === caseNumber);
}

async function handlePatientRowClick(event){
  const archive = event.target.closest("[data-archive-case]");
  if(archive){
    event.stopPropagation();
    const caseNumber = archive.dataset.archiveCase;
    const patient = findCase(caseNumber);
    if (!patient || (!patient.archived && !patient.complete)) return;
    try {
      const action = patient.archived ? "restore" : "archive";
      await window.erasApi.fetch(`/api/cases/${encodeURIComponent(caseNumber)}/${action}/`, { method: "POST", body: "{}" });
      await loadPatients();
    } catch (err) {
      alert(err.message || "Archivierung konnte nicht gespeichert werden.");
    }
    return;
  }
  const row = event.target.closest("[data-case-number]");
  if (!row) return;
  const patient = findCase(row.dataset.caseNumber);
  if (!patient) return;
  updatePreview(patient);
  await goToChecklist(patient);
}

async function handlePatientRowKeydown(event){
  if(event.target.closest("button")) return;
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest("[data-case-number]");
  if (!row) return;
  event.preventDefault();
  const patient = findCase(row.dataset.caseNumber);
  if (!patient) return;
  updatePreview(patient);
  await goToChecklist(patient);
}

document.getElementById("newPatientBtn").addEventListener("click", () => {
  clearModal();
  openModal();
});
document.getElementById("closePatientModal").addEventListener("click", closeModal);
document.getElementById("cancelPatientModal").addEventListener("click", closeModal);
document.getElementById("patientModal").addEventListener("click", event => {
  if (event.target.id === "patientModal") closeModal();
});
document.getElementById("savePatient").addEventListener("click", savePatient);
document.getElementById("patientSearch").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { searchTimer = null; loadPatients(); }, 200);
});
document.getElementById("patientSearchResults").addEventListener("click", handlePatientRowClick);
document.getElementById("patientSearchResults").addEventListener("keydown", handlePatientRowKeydown);

document.getElementById("archiveFilter").addEventListener("click", async event => {
  showArchived = !showArchived;
  event.target.textContent = showArchived ? "Aktive Fälle" : "Archivierte Fälle";
  event.target.setAttribute("aria-pressed", String(showArchived));
  await loadPatients();
});

loadPatients();
setInterval(pollPatients, PATIENT_POLL_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) pollPatients(); });
