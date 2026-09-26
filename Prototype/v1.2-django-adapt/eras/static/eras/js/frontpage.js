const demoPatients = [
  {beneNurse:"Corina Frei", beneDeputy:"Jessica Ambros", surgeon:"Dr. Meier", name:"Muster Anna", patientNumber:"P-10021", caseNumber:"F-78342", opDate:"2026-08-14", procedure:"Radikale Zystektomie mit Ileum-Conduit", progress:82},
  {beneNurse:"Corina Frei", beneDeputy:"Jessica Ambros", surgeon:"Dr. Keller", name:"Beispiel Peter", patientNumber:"P-10022", caseNumber:"F-78343", opDate:"2026-08-21", procedure:"Radikale Zystektomie mit Neoblase", progress:48},
  {beneNurse:"Corina Frei", beneDeputy:"Jessica Ambros", surgeon:"Dr. Schmid", name:"Test Maria", patientNumber:"P-10023", caseNumber:"F-78344", opDate:"2026-09-02", procedure:"Funktionelle Zystektomie", progress:65},
  {beneNurse:"Corina Frei", beneDeputy:"Jessica Ambros", surgeon:"Dr. Weber", name:"Demo Lukas", patientNumber:"P-10024", caseNumber:"F-78345", opDate:"", procedure:"Radikale Zystektomie mit Ileum-Conduit", progress:24},
  {beneNurse:"Corina Frei", beneDeputy:"Jessica Ambros", surgeon:"Dr. Huber", name:"Patientin Eva", patientNumber:"P-10025", caseNumber:"F-78346", opDate:"2026-09-18", procedure:"Radikale Zystektomie mit Neoblase", progress:91},
  {beneNurse:"Corina Frei", beneDeputy:"Jessica Ambros", surgeon:"Dr. Frei", name:"Patient Max", patientNumber:"P-10026", caseNumber:"F-78347", opDate:"2026-10-03", procedure:"Andere Eingriffsart", progress:37}
];

let patients;
try { patients=JSON.parse(localStorage.getItem('bene-patients'))||demoPatients; } catch {patients=demoPatients;}
let showArchived=false;
function caseSummary(patient){
  try{return JSON.parse(localStorage.getItem('bene-case-summary')||'{}')[patient.caseNumber]||{};}catch{return {};}
}
function persistPatients(){localStorage.setItem('bene-patients',JSON.stringify(patients));}

function esc(value){
  return String(value == null ? "" : value).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function patientLabel(patient){
  return [patient.name || "Unbenannte/r Patient*in", patient.caseNumber ? `Fall ${patient.caseNumber}` : "", patient.procedure || ""].filter(Boolean).join(" · ");
}

function checklistUrl(patient){
  const base = document.querySelector("[data-checklist-url]").dataset.checklistUrl;
  const params = new URLSearchParams();
  params.set("patient", patient.name || "");
  params.set("case", patient.caseNumber || "");
  params.set("opdate", patient.opDate || "");
  return `${base}?${params.toString()}`;
}

function goToChecklist(patient){
  window.location.href = checklistUrl(patient);
}

function patientMatches(patient, query){
  const haystack = [
    patient.name,
    patient.patientNumber,
    patient.caseNumber,
    patient.opDate,
    patient.procedure,
    patient.surgeon,
    patient.beneNurse
  ].join(" ").toLowerCase();
  return haystack.includes(query.trim().toLowerCase());
}

function patientRowHTML(patient, idx){
  const summary=caseSummary(patient);
  patient={...patient,progress:summary.progress ?? 0};
  return `
    <div class="patient-row clickable" data-patient-index="${idx}" tabindex="0" role="link" aria-label="Checkliste f?r ${esc(patient.name || "Patient")} ?ffnen">
      <div><strong>${esc(patient.name || "-")}</strong><small>${esc(patient.patientNumber || "")}</small></div>
      <div>${esc(patient.caseNumber || "-")}</div>
      <div>${esc(patient.opDate || "offen")}</div>
      <div>${esc(patient.procedure || "-")}</div>
      <div class="progress-cell">
        <div class="progress-track"><div class="progress-fill" style="width:${Number(patient.progress || 0)}%"></div></div>
        <span class="progress-value">${Number(patient.progress || 0)}%</span>
        <button class="btn" data-archive-case="${idx}" ${!summary.archived && !summary.complete?'disabled title="Alle Checklistenpunkte müssen abgeschlossen sein"':''}>${summary.archived?'Wiederherstellen':'Archivieren'}</button>
      </div>
    </div>
  `;
}

function renderPatients(){
  renderSearchResults();
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
  const input = document.getElementById("patientSearch");
  const results = document.getElementById("patientSearchResults");
  const query = input.value.trim();
  const matches = patients
    .map((patient, idx) => ({patient, idx}))
    .filter(item => !!caseSummary(item.patient).archived===showArchived)
    .filter(item => !query || patientMatches(item.patient, query));
  const label = query ? `${matches.length} Treffer` : (showArchived ? "Archivierte Fälle" : "Aktive Fälle");

  results.innerHTML = `
    <div class="search-results-head">${esc(label)}</div>
    <div class="patient-table search-table">
      ${tableHeaderHTML()}
      ${matches.length ? matches.map(item => patientRowHTML(item.patient, item.idx)).join("") : `<div class="empty-results">Keine passenden Patientinnen oder Patienten gefunden.</div>`}
    </div>
  `;
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

function savePatient(){
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
  if(!patient.name || !patient.caseNumber){alert('Name und eindeutige Fallnummer sind erforderlich.');return;}
  if(patients.some(p=>p.caseNumber===patient.caseNumber)){alert('Diese Fallnummer existiert bereits.');return;}
  patient.progress = 0;
  patients.push(patient);
  persistPatients();
  document.getElementById("patientSearch").value = patient.caseNumber;
  renderPatients();
  updatePreview(patient);
  clearModal();
  closeModal();
}

function handlePatientRowClick(event){
  const archive=event.target.closest('[data-archive-case]');
  if(archive){
    const patient=patients[Number(archive.dataset.archiveCase)];
    const summaries=JSON.parse(localStorage.getItem('bene-case-summary')||'{}');
    const summary=summaries[patient.caseNumber]||{};
    if(!summary.archived && !summary.complete) return;
    summaries[patient.caseNumber]={...summary,archived:!summary.archived};
    try{localStorage.setItem('bene-case-summary',JSON.stringify(summaries));renderPatients();}catch{alert('Archivierung konnte nicht gespeichert werden.');}
    return;
  }
  const row = event.target.closest("[data-patient-index]");
  if (!row) return;
  const patient = patients[parseInt(row.dataset.patientIndex, 10)];
  updatePreview(patient);
  goToChecklist(patient);
}

function handlePatientRowKeydown(event){
  if(event.target.closest("button")) return;
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest("[data-patient-index]");
  if (!row) return;
  event.preventDefault();
  const patient = patients[parseInt(row.dataset.patientIndex, 10)];
  updatePreview(patient);
  goToChecklist(patient);
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
document.getElementById("patientSearch").addEventListener("input", renderSearchResults);
document.getElementById("patientSearchResults").addEventListener("click", handlePatientRowClick);
document.getElementById("patientSearchResults").addEventListener("keydown", handlePatientRowKeydown);


renderPatients();

document.getElementById('archiveFilter').addEventListener('click',event=>{
  showArchived=!showArchived;
  event.target.textContent=showArchived?'Aktive Fälle':'Archivierte Fälle';
  event.target.setAttribute('aria-pressed',String(showArchived));
  renderPatients();
});
