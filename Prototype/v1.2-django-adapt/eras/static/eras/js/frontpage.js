let patients = [];
let showArchived = false;
let searchTimer = null;
const PATIENT_FORM_RULES = JSON.parse(document.getElementById('patient-form-rules').textContent);
const PATIENT_INPUTS = {name:'newPatientName',sex:'newPatientSex',patientNumber:'newPatientNumber',
  caseNumber:'newCaseNumber',opDate:'newOpDate',procedureTypeId:'newProcedure',
  beneNurse:'newBeneNurse',beneDeputy:'newBeneDeputy',surgeon:'newSurgeon'};
let editingPatient = null;
let modalBaseline = '';
let patientSaving = false;
let modalReturnFocus = null;
let pendingPatientDeletion = null;

function patientFormValues(){
  return Object.fromEntries(Object.entries(PATIENT_INPUTS).map(([key,id])=>[key,document.getElementById(id).value]));
}
function patientFormDirty(){ return JSON.stringify(patientFormValues()) !== modalBaseline; }

function patientFieldError(key, message){
  const field = document.getElementById(PATIENT_INPUTS[key]);
  if (!field) return;
  const output = document.getElementById(field.id+'Error');
  output.textContent = message || '';
  field.setAttribute('aria-invalid', String(!!message));
}

function validatePatientField(key){
  const field=document.getElementById(PATIENT_INPUTS[key]);
  const value=field.value.trim();
  let message='';
  if ((key==='name'||key==='caseNumber') && !value) message=key==='name'?'Name ist erforderlich.':'Fallnummer ist erforderlich.';
  if (key==='sex' && (!editingPatient || editingPatient.sex || value) && !PATIENT_FORM_RULES.sexOptions.some(o=>o.value===value)) message='Bitte Männlich oder Weiblich auswählen.';
  if (PATIENT_FORM_RULES.maxLengths[key] && value.length>PATIENT_FORM_RULES.maxLengths[key]) message=`Bitte höchstens ${PATIENT_FORM_RULES.maxLengths[key]} Zeichen eingeben.`;
  if (key==='opDate' && (field.validity.badInput || (value && !/^\d{4}-\d{2}-\d{2}$/.test(value)))) message='Bitte ein gültiges Datum eingeben.';
  patientFieldError(key,message);
  return !message;
}

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
      <div><strong>${esc(patient.name || "-")}</strong><small>${esc(patient.patientNumber || "")} · ${esc(PATIENT_FORM_RULES.sexOptions.find(o=>o.value===patient.sex)?.label || 'Geschlecht nicht erfasst')}</small></div>
      <div>${esc(patient.caseNumber || "-")}</div>
      <div>${esc(patient.opDate || "offen")}</div>
      <div>${esc(patient.procedure || "-")}</div>
      <div class="progress-cell">
        <div class="progress-track"><div class="progress-fill" style="width:${Number(patient.progress || 0)}%"></div></div>
        <span class="progress-value">${Number(patient.progress || 0)}%</span>
        <button type="button" class="btn edit-patient-btn" data-edit-case="${esc(patient.caseNumber)}" aria-label="Stammdaten bearbeiten" title="Stammdaten bearbeiten"><span aria-hidden="true">✎</span></button>
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

function openModal(patient){
  if (document.getElementById('patientModal').classList.contains('open')) return;
  modalReturnFocus = document.activeElement;
  clearModal();
  editingPatient = patient || null;
  if(patient?.procedureTypeId && ![...document.getElementById('newProcedure').options].some(o=>o.value===String(patient.procedureTypeId))){
    document.getElementById('newProcedure').add(new Option(patient.procedure+' (bestehend)',patient.procedureTypeId));
  }
  if (patient) Object.entries(PATIENT_INPUTS).forEach(([key,id])=>{document.getElementById(id).value=patient[key]??'';});
  document.getElementById('newCaseNumber').readOnly = !!patient;
  document.getElementById('newPatientSex').required = !patient || !!patient.sex;
  document.getElementById('patientModalTitle').textContent=patient?'Patient bearbeiten':'Patient erfassen';
  document.getElementById('savePatient').textContent=patient?'Änderungen speichern':'Patient übernehmen';
  document.getElementById('patientEditHint').hidden=!patient;
  document.getElementById('deletePatient').hidden=!patient;
  document.getElementById('patientDeleteConfirmation').hidden=true;
  pendingPatientDeletion=null;
  modalBaseline=JSON.stringify(patientFormValues());
  const modal = document.getElementById("patientModal");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.querySelector('main').inert=true;
  document.getElementById("newPatientName").focus();
}

function closeModal(force=false){
  if (patientSaving) return;
  if (!force && patientFormDirty()){
    document.getElementById('patientDiscardConfirmation').hidden=false;
    document.getElementById('patientForm').inert=true;
    document.getElementById('closePatientModal').disabled=true;
    document.getElementById('continuePatientEditing').focus();
    return;
  }
  const modal = document.getElementById("patientModal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  document.querySelector('main').inert=false;
  document.getElementById('patientDiscardConfirmation').hidden=true;
  document.getElementById('patientDeleteConfirmation').hidden=true;
  pendingPatientDeletion=null;
  document.getElementById('patientForm').inert=false;
  document.getElementById('closePatientModal').disabled=false;
  modalReturnFocus?.focus();
}

function clearModal(){
  Object.values(PATIENT_INPUTS).forEach(id => {
    document.getElementById(id).value = "";
  });
  Object.keys(PATIENT_INPUTS).forEach(key=>patientFieldError(key,''));
  document.getElementById('patientFormMessage').hidden=true;
}

async function savePatient(event){
  event?.preventDefault();
  if (patientSaving) return;
  const rawValues=patientFormValues();
  const baseline=JSON.parse(modalBaseline);
  const valid=Object.keys(PATIENT_INPUTS).map(key=>editingPatient&&rawValues[key]===baseline[key]?true:validatePatientField(key)).every(Boolean);
  if (!valid){document.querySelector('#patientForm [aria-invalid="true"]')?.focus();return;}
  const patient=Object.fromEntries(Object.entries(rawValues).map(([key,value])=>[key,value.trim()]));
  if (editingPatient){
    patient.baseUpdatedAt=editingPatient.updatedAt;
    // PATCH only edited fields: legacy free-text procedure and unrelated data
    // must not be replaced by blank controls when correcting a single value.
    Object.keys(PATIENT_INPUTS).forEach(key=>{if(rawValues[key]===baseline[key])delete patient[key];});
  }
  patientSaving=true;
  document.getElementById('patientForm').inert=true;
  document.getElementById('closePatientModal').disabled=true;
  document.getElementById('savePatient').disabled=true;
  document.getElementById('patientFormMessage').hidden=true;
  try {
    const payload = await window.erasApi.fetch(editingPatient?`/api/cases/${encodeURIComponent(editingPatient.caseNumber)}/`:"/api/patients/", {
      method: editingPatient?'PATCH':"POST",
      body: JSON.stringify(patient)
    });
    document.getElementById("patientSearch").value = payload.case.caseNumber;
    updatePreview(payload.case);
    patientSaving=false;
    closeModal(true);
    await loadPatients();
  } catch (err) {
    document.getElementById('patientForm').inert=false;
    Object.entries(err.payload?.error?.fields||{}).forEach(([key,message])=>patientFieldError(key,message));
    const message=document.getElementById('patientFormMessage');
    message.textContent=err.message || 'Patient konnte nicht gespeichert werden.';
    message.hidden=false;
    document.querySelector('#patientForm [aria-invalid="true"]')?.focus();
  } finally {
    patientSaving=false;
    document.getElementById('patientForm').inert=false;
    document.getElementById('closePatientModal').disabled=false;
    document.getElementById('savePatient').disabled=false;
  }
}

async function requestPatientDeletion(){
  if(!editingPatient||patientSaving)return;
  patientSaving=true;
  document.getElementById('patientForm').inert=true;
  document.getElementById('closePatientModal').disabled=true;
  try{
    // Refresh the exact patient/case snapshot before asking for confirmation.
    const payload=await window.erasApi.fetch(`/api/cases/${encodeURIComponent(editingPatient.caseNumber)}/`);
    pendingPatientDeletion=payload.case;
    document.getElementById('patientDeleteDescription').textContent=`Möchtest du «${pendingPatientDeletion.name}» wirklich löschen? Betroffene Behandlungsfälle: ${pendingPatientDeletion.patientCaseCount}.`;
    document.getElementById('patientDeleteError').hidden=true;
    document.getElementById('confirmPatientDelete').disabled=false;
    document.getElementById('cancelPatientDelete').disabled=false;
    document.getElementById('patientDeleteConfirmation').hidden=false;
    document.getElementById('cancelPatientDelete').focus();
  }catch(err){
    document.getElementById('patientForm').inert=false;
    document.getElementById('closePatientModal').disabled=false;
    const message=document.getElementById('patientFormMessage');
    message.textContent=err.message||'Patient konnte nicht zum Löschen geladen werden.';
    message.hidden=false;
  }finally{patientSaving=false;}
}

function cancelPatientDeletion(){
  if(patientSaving)return;
  document.getElementById('patientDeleteConfirmation').hidden=true;
  document.getElementById('patientForm').inert=false;
  document.getElementById('closePatientModal').disabled=false;
  pendingPatientDeletion=null;
  document.getElementById('deletePatient').focus();
}

async function confirmPatientDeletion(){
  if(!pendingPatientDeletion||patientSaving)return;
  patientSaving=true;
  document.getElementById('confirmPatientDelete').disabled=true;
  document.getElementById('cancelPatientDelete').disabled=true;
  try{
    await window.erasApi.fetch(`/api/cases/${encodeURIComponent(pendingPatientDeletion.caseNumber)}/`,{
      method:'DELETE',body:JSON.stringify({confirmedPatientId:pendingPatientDeletion.patientId,deletionToken:pendingPatientDeletion.deletionToken})
    });
    patientSaving=false;
    closeModal(true);
    editingPatient=null;
    document.getElementById('patientSearch').value='';
    updatePreview(null);
    // Remove the edit link to the now-deleted patient from the address bar.
    if(new URLSearchParams(window.location.search).has('edit')) window.history.replaceState(null,'',window.location.pathname);
    await loadPatients();
  }catch(err){
    const message=document.getElementById('patientDeleteError');
    message.textContent=err.message||'Patient konnte nicht gelöscht werden.';
    message.hidden=false;
    // A stale/expired confirmation requires opening a fresh confirmation box.
    if(err.status===409||err.status===422) pendingPatientDeletion=null;
  }finally{
    patientSaving=false;
    document.getElementById('confirmPatientDelete').disabled=!pendingPatientDeletion;
    document.getElementById('cancelPatientDelete').disabled=false;
  }
}

function findCase(caseNumber){
  return patients.find(patient => patient.caseNumber === caseNumber);
}

async function handlePatientRowClick(event){
  const edit=event.target.closest('[data-edit-case]');
  if(edit){
    event.stopPropagation();
    try{ const payload=await window.erasApi.fetch(`/api/cases/${encodeURIComponent(edit.dataset.editCase)}/`); openModal(payload.case); }
    catch(err){alert(err.message || 'Patient konnte nicht geladen werden.');}
    return;
  }
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

Object.entries(PATIENT_INPUTS).forEach(([key,id])=>{
  const field=document.getElementById(id);
  if(PATIENT_FORM_RULES.maxLengths[key]) field.maxLength=PATIENT_FORM_RULES.maxLengths[key];
  const error=document.createElement('small');
  error.id=id+'Error'; error.className='field-error'; error.setAttribute('aria-live','polite');
  field.after(error); field.setAttribute('aria-describedby',error.id);
  field.addEventListener('blur',()=>validatePatientField(key));
  field.addEventListener('input',()=>{if(field.getAttribute('aria-invalid')==='true')validatePatientField(key);});
});
document.getElementById('newPatientName').required=true;
document.getElementById('newCaseNumber').required=true;
document.getElementById('newPatientName').previousElementSibling.textContent='Patient*in Name *';
document.getElementById('newCaseNumber').previousElementSibling.textContent='Patient*in Fallnummer *';
document.getElementById("newPatientBtn").addEventListener("click", () => openModal());
document.getElementById("closePatientModal").addEventListener("click", () => closeModal());
document.getElementById("cancelPatientModal").addEventListener("click", () => closeModal());
document.getElementById('continuePatientEditing').addEventListener('click',()=>{
  document.getElementById('patientDiscardConfirmation').hidden=true;
  document.getElementById('patientForm').inert=false;
  document.getElementById('closePatientModal').disabled=false;
  document.getElementById('newPatientName').focus();
});
document.getElementById('discardPatientChanges').addEventListener('click',()=>closeModal(true));
document.getElementById('deletePatient').addEventListener('click',requestPatientDeletion);
document.getElementById('cancelPatientDelete').addEventListener('click',cancelPatientDeletion);
document.getElementById('confirmPatientDelete').addEventListener('click',confirmPatientDeletion);
document.getElementById('patientModal').addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();return;}
  if(event.key!=='Tab')return;
  const controls=[...event.currentTarget.querySelectorAll('button,input,select')].filter(el=>!el.disabled&&!el.closest('[hidden]')&&!el.closest('[inert]'));
  const first=controls[0],last=controls.at(-1);
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
});
window.addEventListener('beforeunload',event=>{
  if(document.getElementById('patientModal').classList.contains('open')&&(patientSaving||patientFormDirty())){event.preventDefault();event.returnValue='';}
});
document.getElementById('patientForm').addEventListener('submit',savePatient);
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
const editCase=new URLSearchParams(window.location.search).get('edit');
if(editCase) window.erasApi.fetch(`/api/cases/${encodeURIComponent(editCase)}/`).then(payload=>openModal(payload.case)).catch(err=>alert(err.message));
setInterval(pollPatients, PATIENT_POLL_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) pollPatients(); });
