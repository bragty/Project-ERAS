/* ============================= DATA ============================= */

/* The checklist structure and its texts come from apps/checklist/definition.json
   (texts possibly edited in the Django admin), embedded by the page template.
   Fields are referenced by key and resolved here; preop items keep their short
   id ("pbm" for "t1:pbm"), pathway items their full id as pathId. */
const CHECKLIST_DEFINITION = JSON.parse(document.getElementById('checklist-definition').textContent);

function resolveFields(refs){
  return refs.map(ref => typeof ref === "string"
    ? {key:ref, ...CHECKLIST_DEFINITION.fields[ref]}
    : {...CHECKLIST_DEFINITION.fields[ref.key], ...ref});
}

function definitionItem(item, idProps){
  if (item.divider) return {divider:item.divider, dividerId:item.id};
  const {id, fields, ...rest} = item;
  return {...rest, ...idProps, ...(fields ? {fields:resolveFields(fields)} : {})};
}

const CHECKLIST1 = CHECKLIST_DEFINITION.preop.map(it => definitionItem(it, {id:it.id.replace(/^t1:/, "")}));

const PHASES = CHECKLIST_DEFINITION.phases.map(ph => ({
  ...ph,
  roles: ph.roles.map(r => ({...r, items: r.items.map(it => definitionItem(it, {pathId:it.id}))}))
}));

/* ============================= STATE ============================= */
const LAB_OPTIONS = [
  "Hb", "Leukozyten", "Thrombozyten", "Quick / INR", "Ferritin", "Transferrinsättigung",
  "Kreatinin", "Natrium", "Kalium", "CRP", "Troponin T", "BNP", "Albumin", "Anderer Wert"
];
const LAB_ID_BY_LABEL = {
  "Hb":"hb","Leukozyten":"leukozyten","Thrombozyten":"thrombozyten","Quick / INR":"quick_inr",
  "Ferritin":"ferritin","Transferrinsättigung":"transferrinsaettigung","Kreatinin":"kreatinin","Natrium":"natrium",
  "Kalium":"kalium","CRP":"crp","Troponin T":"troponin_t","BNP":"bnp","Albumin":"albumin","Anderer Wert":"other"
};
const LAB_IMPORT_OPTIONS = LAB_OPTIONS.filter(label => label !== "Anderer Wert");
let LAB_IMPORT_PREVIEW = null;
let LAB_IMPORT_BUSY = false;

// Same limit as NOTE_MAX_LENGTH in apps/checklist/engine.py.
const NOTE_MAX_LENGTH = 2000;

let STATE = { patientName:"", opDate:"", checked:{}, openBlocks:{}, answers:{}, notes:{}, labs:[], suchtmittel:[] };
let saveTimer = null;

/* Everything rule-based (flags, BMI, referrals, questionnaire totals, whether a
   tick is valid) is computed by the backend (apps/checklist/rules.py) on every
   save and only displayed here. DERIVED holds the last server result,
   ITEM_ERRORS the reasons why the server refused a tick, per item. */
let DERIVED = {};
let ITEM_ERRORS = {};

function esc(s){
  return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// Texts from the definition are plain text; only links written as
// [Linktext](https://…) become anchors.
function richText(s){
  return esc(s).replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function preopItemIds(){
  return CHECKLIST1.filter(i=>!i.divider).map(i => "t1:"+i.id);
}

function pathItemIds(){
  const ids = [];
  PHASES.forEach(ph => ph.roles.forEach(r => r.items.forEach((it,idx) => !it.divider && ids.push(it.pathId))));
  return ids;
}

function allItemIds(){
  return preopItemIds().concat(pathItemIds());
}

function fieldsHTML(fields){
  return `<div class="fields">${fields.map(f=>{
    const val = STATE.answers[f.key];
    if (f.type === "select"){
      const opts = ['<option value="">–</option>'].concat(
        f.options.map(o => { const value=typeof o==="object" ? o.value : o; const label=typeof o==="object" ? o.label : o; return `<option value="${esc(value)}" ${String(val)===String(value)?"selected":""}>${esc(label)}</option>`; })
      );
      return `<label class="field"><span>${esc(f.label)}</span><select data-fkey="${f.key}">${opts.join("")}</select></label>`;
    }
    const minAttr = f.min!==undefined ? ` min="${f.min}"` : "";
    const maxAttr = f.max!==undefined ? ` max="${f.max}"` : "";
    const stepAttr = f.step!==undefined ? ` step="${f.step}"` : "";
    return `<label class="field"><span>${esc(f.label)}</span><input type="${f.type}" data-fkey="${f.key}" value="${esc(val ?? "")}" placeholder="${esc(f.placeholder||"")}"${minAttr}${maxAttr}${stepAttr}${f.readonly?' readonly aria-readonly="true"':''}></label>`;
  }).join("")}</div>`;
}

function optionsHTML(options, val){
  return ['<option value="">–</option>'].concat(
    options.map(o => `<option value="${esc(o)}" ${val===o?"selected":""}>${esc(o)}</option>`)
  ).join("");
}

function currentCaseNumber(){
  return new URLSearchParams(window.location.search).get('case') || '';
}

function formatMeasurementTime(value){
  if(!value) return 'Messzeitpunkt nicht erkannt';
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString('de-CH',{dateStyle:'short',timeStyle:'short'}) : value;
}

function labImportPreviewHTML(){
  if(!LAB_IMPORT_PREVIEW) return '';
  const patient = LAB_IMPORT_PREVIEW.patientMatch || {status:'unverified',message:'Patientenzuordnung nicht geprüft.'};
  const times = LAB_IMPORT_PREVIEW.measurementTimes || [];
  const selectedTime = LAB_IMPORT_PREVIEW.selectedTime ?? times[0] ?? '';
  const suggestions = (LAB_IMPORT_PREVIEW.suggestions || []).filter(item => !selectedTime || item.measurementAt === selectedTime);
  const patientClass = patient.status === 'match' ? 'ok' : patient.status === 'mismatch' ? 'error' : 'warning';
  const globalWarnings = (LAB_IMPORT_PREVIEW.warnings || []).map(w=>`<li>${esc(w)}</li>`).join('');
  return `<div class="lab-import-preview" data-lab-import-preview>
    <div class="lab-import-preview-head">
      <strong>Importvorschau</strong>
      <span>${esc(LAB_IMPORT_PREVIEW.fileName || '')}</span>
    </div>
    <div class="lab-import-patient ${patientClass}">${esc(patient.message || '')}</div>
    ${patient.status==='unverified' ? `<label class="lab-import-confirm"><input type="checkbox" data-lab-patient-confirm> Patient/Fall wurde anhand des geöffneten Falls manuell kontrolliert.</label>` : ''}
    ${times.length>1 ? `<label class="field lab-import-time"><span>Messzeitpunkt</span><select data-lab-import-time>${times.map(t=>`<option value="${esc(t)}" ${t===selectedTime?'selected':''}>${esc(formatMeasurementTime(t))}</option>`).join('')}</select></label>` : ''}
    ${globalWarnings ? `<ul class="lab-import-warnings">${globalWarnings}</ul>` : ''}
    <div class="lab-import-results">
      ${suggestions.length ? suggestions.map((item,index)=>{
        const sourceIndex = (LAB_IMPORT_PREVIEW.suggestions||[]).indexOf(item);
        const hasConflict = (item.existingConflicts || []).length>0;
        const disabled = !!item.alreadyImported || !!LAB_IMPORT_PREVIEW.blocked;
        const checked = item.status==='ready' && !hasConflict && !disabled ? 'checked' : '';
        const warnings = (item.warnings||[]).map(w=>`<li>${esc(w)}</li>`).join('');
        const conflict = hasConflict ? `<div class="lab-import-conflict">Vorhanden: ${(item.existingConflicts||[]).map(c=>`${esc(c.value)} ${esc(c.unit)}`).join(', ')}. Bei Auswahl wird der erste vorhandene Wert dieses Parameters ersetzt.</div>` : '';
        const key = `${item.labId}|${item.measurementAt||''}|${item.sourcePage}|${sourceIndex}`;
        return `<article class="lab-import-result ${item.status==='review'?'review':''}">
          <label class="lab-import-select"><input type="checkbox" data-lab-import-select="${esc(key)}" data-lab-import-index="${sourceIndex}" ${checked} ${disabled?'disabled':''}> Übernehmen</label>
          <div class="lab-import-grid">
            <label><span>Laborparameter</span><select disabled aria-label="Erkannter Laborparameter" data-lab-preview-index="${sourceIndex}" data-lab-preview-field="labLabel">${optionsHTML(LAB_IMPORT_OPTIONS,item.labLabel)}</select><small>Erkannt: ${esc(item.originalLabel||'')}</small></label>
            <label><span>Wert</span><div class="lab-import-value"><select data-lab-preview-index="${sourceIndex}" data-lab-preview-field="comparisonOperator">${['','<','>','<=','>='].map(op=>`<option value="${esc(op)}" ${op===(item.comparisonOperator||'')?'selected':''}>${esc(op||'=')}</option>`).join('')}</select><input type="text" data-lab-preview-index="${sourceIndex}" data-lab-preview-field="normalizedValue" value="${esc(item.normalizedValue||'')}"></div><small>Original: ${esc(item.originalValue||'')}</small></label>
            <label><span>Einheit</span><input type="text" data-lab-preview-index="${sourceIndex}" data-lab-preview-field="normalizedUnit" value="${esc(item.normalizedUnit||'')}"><small>Original: ${esc(item.originalUnit||'')}</small></label>
            <label><span>Messzeitpunkt</span><input type="datetime-local" data-lab-preview-index="${sourceIndex}" data-lab-preview-field="measurementAt" value="${esc(item.measurementAt||'')}"><small>Seite ${esc(item.sourcePage)}</small></label>
          </div>
          ${conflict}
          ${warnings ? `<ul class="lab-import-warnings">${warnings}</ul>` : ''}
          <details class="lab-import-source"><summary>Fundstelle anzeigen</summary><code>${esc(item.sourceExcerpt||'Keine Fundstelle verfügbar')}</code></details>
        </article>`;
      }).join('') : '<p class="lab-import-empty">Für diesen Messzeitpunkt wurden keine unterstützten Werte erkannt.</p>'}
    </div>
    <div class="lab-import-actions">
      <button type="button" class="btn" data-lab-import-cancel>Abbrechen</button>
      <button type="button" class="btn primary" data-lab-import-apply ${LAB_IMPORT_PREVIEW.blocked?'disabled':''}>Werte übernehmen</button>
    </div>
  </div>`;
}

function labImportHTML(){
  return `<section class="lab-import-box" aria-label="Laborbericht importieren">
    <div class="lab-dropzone ${LAB_IMPORT_BUSY?'busy':''}" data-lab-dropzone role="button" tabindex="0" aria-label="Laborbericht als PDF oder Bild auswählen oder hier ablegen">
      <input type="file" accept="application/pdf,image/png,image/jpeg" data-lab-file hidden>
      <strong>Laborbericht importieren</strong>
      <span>${LAB_IMPORT_BUSY ? 'Bericht wird verarbeitet …' : 'KISIM-Laborbericht im vereinbarten Format als PDF oder Bild ablegen.'}</span>
      <button type="button" class="btn" data-lab-file-button ${LAB_IMPORT_BUSY?'disabled':''}>Datei auswählen</button>
    </div>
    <div class="lab-import-status" data-lab-import-status aria-live="polite">${LAB_IMPORT_PREVIEW ? 'Bericht verarbeitet. Bitte erkannte Werte prüfen.' : ''}</div>
    ${labImportPreviewHTML()}
  </section>`;
}

function labRowsHTML(){
  const rows = STATE.labs && STATE.labs.length ? STATE.labs : [{type:"", value:"", unit:""}];
  STATE.labs = rows;
  return `${labImportHTML()}<div class="dynamic-list" data-dynamic="labs">
    ${rows.map((row, idx) => `<div class="dynamic-row">
      <label class="field"><span>Laborwert</span><select data-lab-idx="${idx}" data-lab-key="type">${optionsHTML(LAB_OPTIONS, row.type)}</select></label>
      <label class="field"><span>Wert</span><input type="text" data-lab-idx="${idx}" data-lab-key="value" value="${esc(row.value||"")}"></label>
      <label class="field"><span>Einheit</span><input type="text" data-lab-idx="${idx}" data-lab-key="unit" value="${esc(row.unit||"")}" placeholder="z.B. g/L"></label>
      <button type="button" class="icon-btn" data-remove-lab="${idx}" aria-label="Laborwert entfernen">×</button>
    </div>`).join("")}
    <button type="button" class="add-row-btn" data-add-lab>+ Laborwert hinzufügen</button>
  </div>`;
}

async function processLabImport(file){
  if(!file || LAB_IMPORT_BUSY) return;
  const caseNumber = currentCaseNumber();
  if(!caseNumber){
    alert('Laborberichte können nur innerhalb eines geöffneten Behandlungsfalls importiert werden.');
    return;
  }
  LAB_IMPORT_BUSY = true;
  LAB_IMPORT_PREVIEW = null;
  renderChecklist1();
  try{
    const body = new FormData();
    body.append('file', file);
    const payload = await window.erasApi.fetch(`/api/cases/${encodeURIComponent(caseNumber)}/labs/import/`, {method:'POST', body});
    payload.selectedTime = (payload.measurementTimes || [])[0] || '';
    LAB_IMPORT_PREVIEW = payload;
  }catch(err){
    LAB_IMPORT_PREVIEW = null;
    alert(err?.message || 'Laborbericht konnte nicht verarbeitet werden.');
  }finally{
    LAB_IMPORT_BUSY = false;
    renderChecklist1();
    renderDerived();
  }
}

function applyLabImport(){
  if(!LAB_IMPORT_PREVIEW || LAB_IMPORT_PREVIEW.blocked) return;
  const patient = LAB_IMPORT_PREVIEW.patientMatch || {};
  if(patient.status==='unverified'){
    const confirmed = document.querySelector('[data-lab-patient-confirm]')?.checked;
    if(!confirmed){
      alert('Bitte bestätigen, dass der Bericht zum aktuell geöffneten Patienten/Fall gehört.');
      return;
    }
  }
  const checkedIndexes = new Set([...document.querySelectorAll('[data-lab-import-index]:checked')].map(el=>Number(el.dataset.labImportIndex)));
  const selected = (LAB_IMPORT_PREVIEW.suggestions||[]).filter((item,index)=>checkedIndexes.has(index) && !item.alreadyImported);
  if(!selected.length){ alert('Keine Werte zur Übernahme ausgewählt.'); return; }
  const invalid = selected.find(item=>!LAB_IMPORT_OPTIONS.includes(item.labLabel) || LAB_ID_BY_LABEL[item.labLabel]!==item.labId || !/^[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test(String(item.normalizedValue??'').trim()) || !['','<','>','<=','>='].includes(item.comparisonOperator||'') || !String(item.normalizedUnit||'').trim());
  if(invalid){
    alert('Bitte für alle ausgewählten Importwerte Laborparameter, Wert und Einheit vollständig prüfen.');
    return;
  }

  if(new Set(selected.map(item=>item.labId)).size !== selected.length){
    alert('Mehrere Ergebnisse für denselben Laborparameter ausgewählt. Bitte genau eines auswählen.');
    return;
  }
  // A manual edit made while the import was running also needs confirmation.
  const conflicts = selected.filter(item=>STATE.labs.some(row=>row.type===item.labLabel && String(row.value||'').trim()));
  if(conflicts.length && !confirm('Vorhandene Werte ersetzen: '+conflicts.map(item=>item.labLabel).join(', ')+'?')) return;

  selected.forEach(item=>{
    const value = `${item.comparisonOperator||''}${item.normalizedValue||''}`;
    const meta = {
      sourceHash: item.sourceHash,
      labId: item.labId,
      measurementAt: item.measurementAt || null,
      sourcePage: item.sourcePage,
      extractionMethod: item.extractionMethod,
      originalLabel: item.originalLabel,
      originalValue: item.originalValue,
      originalUnit: item.originalUnit,
      templateId: item.templateId,
      confirmedAt: new Date().toISOString()
    };
    const exactDuplicate = STATE.labs.find(row=>{
      const existing = row.importMeta || {};
      return existing.sourceHash===meta.sourceHash && existing.labId===meta.labId && existing.measurementAt===meta.measurementAt;
    });
    if(exactDuplicate) return;

    const conflictIndex = STATE.labs.findIndex(row=>row.type===item.labLabel && String(row.value||'').trim());
    const target = conflictIndex>=0 ? conflictIndex : STATE.labs.findIndex(row=>!row.type && !String(row.value||'').trim() && !String(row.unit||'').trim());
    const row = {type:item.labLabel, value, unit:item.normalizedUnit||item.originalUnit||'', importMeta:meta};
    if(target>=0) STATE.labs[target]=row; else STATE.labs.push(row);
  });
  delete STATE.checked['t1:laborwerte'];
  LAB_IMPORT_PREVIEW = null;
  renderChecklist1();
  updateProgress();
  renderDerived();
  scheduleSave();
}

function suchtRowsHTML(){
  const rows = STATE.suchtmittel && STATE.suchtmittel.length ? STATE.suchtmittel : [{substance:"", frequency:""}];
  STATE.suchtmittel = rows;
  return `<div class="dynamic-list" data-dynamic="suchtmittel">
    ${rows.map((row, idx) => `<div class="dynamic-row">
      <label class="field"><span>Droge / Substanz</span><input type="text" data-sucht-idx="${idx}" data-sucht-key="substance" value="${esc(row.substance||"")}"></label>
      <label class="field"><span>Häufigkeit</span><input type="text" data-sucht-idx="${idx}" data-sucht-key="frequency" value="${esc(row.frequency||"")}" placeholder="z.B. täglich"></label>
      <label class="field"><span>Bemerkung</span><input type="text" data-sucht-idx="${idx}" data-sucht-key="note" value="${esc(row.note||"")}"></label>
      <button type="button" class="icon-btn" data-remove-sucht="${idx}" aria-label="Droge entfernen">×</button>
    </div>`).join("")}
    <button type="button" class="add-row-btn" data-add-sucht>+ Droge hinzufügen</button>
  </div>`;
}

function customHTML(kind){
  if (kind === "labs") return labRowsHTML();
  if (kind === "suchtmittel") return suchtRowsHTML();
  return "";
}

function itemHTML(id, title, opts){
  opts = opts || {};
  const { fields, flagRule, custom } = opts;
  const checked = !!STATE.checked[id];
  const detail = (opts.detail || []).map(d => `<li>${richText(d)}</li>`);
  if (opts.widget === "bmi") detail.push('<li>BMI: <output id="bmi">Grösse und Gewicht erfassen</output></li>');
  if (opts.scoreDescription) detail.push(`<li><p class="questionnaire-description" data-score-description="${opts.id}" aria-live="polite"></p></li>`);
  const detailHTML = detail.length ? `<div class="item-detail"><ul>${detail.join("")}</ul></div>` : "";
  const fieldsStr = fields && fields.length ? fieldsHTML(fields) : "";
  const customStr = custom ? customHTML(custom) : "";
  const flagHTML = flagRule ? `<div class="flag-box" data-rule="${flagRule}"></div>` : "";
  const errorsHTML = itemErrorsHTML(id, fields || []);
  const noteVal = STATE.notes[id] || "";
  const noteOpen = noteVal ? "open" : "";
  return `<div class="item ${checked?'checked':''}" data-id="${id}">
    <input type="checkbox" ${checked?'checked':''} data-id="${id}">
    <div class="item-body">
      <div class="item-title" data-id="${id}">${esc(title)}</div>
      ${opts.questionnaire ? `<details class="questionnaire" data-questionnaire="${opts.id}" ${(STATE.openBlocks['questionnaire:'+opts.id]&&!checked)||ITEM_ERRORS[id]?'open':''}><summary>Fragebogen ausfüllen <span data-questionnaire-result="${opts.id}"></span></summary>` : ''}
      <div class="item-content">${detailHTML}
      ${fieldsStr}
      ${customStr}
      ${flagHTML}
      ${errorsHTML}
      <button type="button" class="note-toggle" data-notetoggle="${id}">${noteVal? '– Notiz ausblenden' : '+ Notiz'}</button>
      <div class="note-wrap ${noteOpen}" data-notewrap="${id}">
        <textarea data-notekey="${id}" rows="2" maxlength="${NOTE_MAX_LENGTH}" placeholder="Freitext-Notiz…">${esc(noteVal)}</textarea>
      </div></div>
      ${opts.questionnaire ? "</details>" : ""}
    </div>
  </div>`;
}

function itemErrorsHTML(id, fields){
  const errors = ITEM_ERRORS[id];
  if (!errors) return "";
  const lines = Object.entries(errors).map(([key, message]) => {
    const field = fields.find(f => f.key === key);
    return `<li>${field ? `${esc(field.label)}: ` : ""}${esc(message)}</li>`;
  });
  return `<div class="item-errors" role="alert"><strong>Kann nicht abgehakt werden:</strong><ul>${lines.join("")}</ul></div>`;
}

function dividerHTML(label, id){
  return `<div class="group-divider" data-divider="${esc(id)}">${esc(label)}</div>`;
}

function renderChecklist1(){
  const el = document.getElementById('items-t1');
  el.innerHTML = CHECKLIST1.map(i => i.divider ? dividerHTML(i.divider, i.dividerId) : itemHTML("t1:"+i.id, i.title, i)).join("");
}

function renderPhases(){
  const container = document.getElementById('phases-t2');
  container.innerHTML = PHASES.map(ph => {
    const rolesHTML = ph.roles.map(r => {
      const isOpen = STATE.openBlocks[r.id] !== false; // default open
      let itemsHTML;
      if (r.jump){
        itemsHTML = `<div style="padding:6px 0 4px;">
          <div style="font-size:13px;color:var(--ink-soft);">Wird im Tab «Prä-OP Checkliste» separat abgehakt.</div>
          <button class="jumplink" data-jump="t1">Zur Prä-OP Checkliste →</button>
        </div>`;
      } else {
        itemsHTML = r.items.map((it,idx) => it.divider ? dividerHTML(it.divider, it.dividerId) : itemHTML(it.pathId, it.title, it)).join("");
      }
      const total = r.items.filter(it=>!it.divider).length;
      const done = r.items.reduce((n,it,idx)=> n + (STATE.checked[it.pathId] ? 1:0), 0);
      const countLabel = r.jump ? "" : `<span class="role-count">${done}/${total}</span>`;
      return `<div class="role-block ${isOpen?'open':''}" data-role="${r.id}">
        <div class="role-head" data-role-toggle="${r.id}">
          <span class="chev">▸</span>
          <span class="role-title">${esc(r.title)}${r.note?`<span style="font-weight:400;color:var(--ink-soft);"> — ${esc(r.note)}</span>`:''}</span>
          ${countLabel}
        </div>
        <div class="role-items">${itemsHTML}</div>
      </div>`;
    }).join("");

    const totalItems = ph.roles.reduce((n,r)=> n + r.items.filter(it=>!it.divider).length, 0);
    const doneItems = ph.roles.reduce((n,r)=> n + r.items.reduce((m,it,idx)=> m + (STATE.checked[it.pathId]?1:0),0), 0);

    return `<div class="phase-head" data-phase="${esc(ph.id)}">
        <span class="phase-tag">${esc(ph.tag)}</span>
        <h2>${esc(ph.title)}</h2>
        <span class="phase-progress">${doneItems}/${totalItems}</span>
      </div>
      ${rolesHTML}`;
  }).join("");
}

function scrollToChecklistTarget(tab, selector){
  switchTab(tab);
  window.requestAnimationFrame(() => {
    const target = document.querySelector(selector);
    if (!target) return;

    const roleBlock = target.closest('.role-block');
    if (roleBlock){
      roleBlock.classList.add('open');
      STATE.openBlocks[roleBlock.dataset.role] = true;
      scheduleSave();
    }

    target.scrollIntoView({behavior:'smooth', block:'start'});
  });
}

function attachHandlers(){
  document.body.addEventListener('click', (e) => {
    const fileButton = e.target.closest('[data-lab-file-button]');
    if (fileButton){
      fileButton.closest('[data-lab-dropzone]')?.querySelector('[data-lab-file]')?.click();
      return;
    }
    const applyImport = e.target.closest('[data-lab-import-apply]');
    if (applyImport){ applyLabImport(); return; }
    const cancelImport = e.target.closest('[data-lab-import-cancel]');
    if (cancelImport){ LAB_IMPORT_PREVIEW=null; renderChecklist1(); renderDerived(); return; }
    const dropzoneClick = e.target.closest('[data-lab-dropzone]');
    if (dropzoneClick && !e.target.closest('button,input,select')){
      dropzoneClick.querySelector('[data-lab-file]')?.click();
      return;
    }
    const cb = e.target.closest('input[type=checkbox]');
    if (cb && cb.dataset.id){
      // The server validates the tick on save; if fields are missing it removes
      // the tick again and returns the reasons (shown via ITEM_ERRORS).
      STATE.checked[cb.dataset.id] = cb.checked;
      delete ITEM_ERRORS[cb.dataset.id];
      saveNow();
      updateProgress();
      const row = cb.closest('.item');
      if (row) { row.classList.toggle('checked', cb.checked); const disclosure=row.querySelector('details.questionnaire'); if(disclosure && cb.checked) disclosure.open=false; }
      const roleBlock = cb.closest('.role-block');
      if (roleBlock) refreshRoleCount(roleBlock.dataset.role);
      return;
    }
    const titleEl = e.target.closest('.item-title');
    if (titleEl && titleEl.dataset.id){
      const box = document.querySelector(`input[type=checkbox][data-id="${titleEl.dataset.id}"]`);
      if (box){ box.click(); }
      return;
    }
    const roleToggle = e.target.closest('[data-role-toggle]');
    if (roleToggle){
      const id = roleToggle.dataset.roleToggle;
      const block = roleToggle.closest('.role-block');
      block.classList.toggle('open');
      STATE.openBlocks[id] = block.classList.contains('open');
      scheduleSave();
      return;
    }
    const jump = e.target.closest('[data-jump]');
    if (jump){
      switchTab(jump.dataset.jump);
      return;
    }
    const addLab = e.target.closest('[data-add-lab]');
    if (addLab){
      STATE.labs.push({type:"", value:"", unit:""});
      renderChecklist1();
      renderDerived();
      scheduleSave();
      return;
    }
    const removeLab = e.target.closest('[data-remove-lab]');
    if (removeLab){
      const idx = parseInt(removeLab.dataset.removeLab, 10);
      STATE.labs.splice(idx, 1);
      if (!STATE.labs.length) STATE.labs.push({type:"", value:"", unit:""});
      renderChecklist1();
      renderDerived();
      scheduleSave();
      return;
    }
    const addSucht = e.target.closest('[data-add-sucht]');
    if (addSucht){
      STATE.suchtmittel.push({substance:"", frequency:"", note:""});
      renderChecklist1();
      renderDerived();
      scheduleSave();
      return;
    }
    const removeSucht = e.target.closest('[data-remove-sucht]');
    if (removeSucht){
      const idx = parseInt(removeSucht.dataset.removeSucht, 10);
      STATE.suchtmittel.splice(idx, 1);
      if (!STATE.suchtmittel.length) STATE.suchtmittel.push({substance:"", frequency:"", note:""});
      renderChecklist1();
      renderDerived();
      scheduleSave();
      return;
    }
    const nt = e.target.closest('[data-notetoggle]');
    if (nt){
      const id = nt.dataset.notetoggle;
      const wrap = document.querySelector(`[data-notewrap="${id}"]`);
      wrap.classList.toggle('open');
      nt.textContent = wrap.classList.contains('open') ? '– Notiz ausblenden' : '+ Notiz';
      if (wrap.classList.contains('open')){
        const ta = wrap.querySelector('textarea');
        if (ta) ta.focus();
      }
      return;
    }
  });

  document.querySelectorAll('[data-rail-target]').forEach(btn => {
    btn.addEventListener('click', () => {
      scrollToChecklistTarget(btn.dataset.railTab, btn.dataset.railTarget);
    });
  });

  document.body.addEventListener('input', (e) => {
    const previewField = e.target.closest('[data-lab-preview-field]');
    if (previewField && LAB_IMPORT_PREVIEW){
      const item = LAB_IMPORT_PREVIEW.suggestions?.[Number(previewField.dataset.labPreviewIndex)];
      if(item){
        item[previewField.dataset.labPreviewField] = previewField.value;
        if(previewField.dataset.labPreviewField==='labLabel') item.labId = LAB_ID_BY_LABEL[previewField.value] || 'other';
      }
      return;
    }
    const f = e.target.closest('[data-fkey]');
    if (f){
      STATE.answers[f.dataset.fkey] = f.value;
      invalidateConfirmations(itemIdsUsingField(f.dataset.fkey));
      scheduleSave();
      renderDerived();
      return;
    }
    const lab = e.target.closest('[data-lab-idx]');
    if (lab){
      const idx = parseInt(lab.dataset.labIdx, 10);
      STATE.labs[idx][lab.dataset.labKey] = lab.value;
      invalidateConfirmations(['t1:laborwerte']);
      scheduleSave();
      return;
    }
    const sucht = e.target.closest('[data-sucht-idx]');
    if (sucht){
      const idx = parseInt(sucht.dataset.suchtIdx, 10);
      STATE.suchtmittel[idx][sucht.dataset.suchtKey] = sucht.value;
      scheduleSave();
      return;
    }
    const n = e.target.closest('[data-notekey]');
    if (n){
      STATE.notes[n.dataset.notekey] = n.value;
      scheduleSave();
      return;
    }
  });

  document.body.addEventListener('change', (e) => {
    const fileInput = e.target.closest('[data-lab-file]');
    if(fileInput){ processLabImport(fileInput.files?.[0]); return; }
    const importTime = e.target.closest('[data-lab-import-time]');
    if(importTime && LAB_IMPORT_PREVIEW){
      LAB_IMPORT_PREVIEW.selectedTime = importTime.value;
      renderChecklist1();
      return;
    }
    const previewField = e.target.closest('[data-lab-preview-field]');
    if (previewField && LAB_IMPORT_PREVIEW){
      const item = LAB_IMPORT_PREVIEW.suggestions?.[Number(previewField.dataset.labPreviewIndex)];
      if(item){
        item[previewField.dataset.labPreviewField] = previewField.value;
        if(previewField.dataset.labPreviewField==='labLabel') item.labId = LAB_ID_BY_LABEL[previewField.value] || 'other';
      }
      return;
    }
    const f = e.target.closest('select[data-fkey]');
    if (f){
      STATE.answers[f.dataset.fkey] = f.value;
      scheduleSave();
      renderDerived();
    }
    const lab = e.target.closest('select[data-lab-idx]');
    if (lab){
      const idx = parseInt(lab.dataset.labIdx, 10);
      STATE.labs[idx][lab.dataset.labKey] = lab.value;
      scheduleSave();
    }
  });

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  document.getElementById('pname').addEventListener('input', e => { STATE.patientName = e.target.value; scheduleSave(); });
  document.getElementById('opdate').addEventListener('input', e => { STATE.opDate = e.target.value; scheduleSave(); });

  document.getElementById('printBtn').addEventListener('click', () => window.print());
  document.getElementById('resetBtn').addEventListener('click', () => {
    if (confirm('Wirklich zurücksetzen? Alle Häkchen, Eingaben und Notizen dieser Checkliste werden gelöscht.')){
      STATE = emptyState();
      document.getElementById('pname').value = "";
      document.getElementById('opdate').value = "";
      renderChecklist1();
      renderPhases();
      updateProgress();
      renderDerived();
      saveState(true);
    }
  });

  document.body.addEventListener('keydown', e=>{
    const zone=e.target.closest('[data-lab-dropzone]');
    if(zone && (e.key==='Enter'||e.key===' ')){
      e.preventDefault();
      zone.querySelector('[data-lab-file]')?.click();
    }
  });
  document.body.addEventListener('dragover', e=>{
    const zone=e.target.closest('[data-lab-dropzone]');
    if(!zone) return;
    e.preventDefault();
    zone.classList.add('dragover');
  });
  document.body.addEventListener('dragleave', e=>{
    e.target.closest('[data-lab-dropzone]')?.classList.remove('dragover');
  });
  document.body.addEventListener('drop', e=>{
    const zone=e.target.closest('[data-lab-dropzone]');
    if(!zone) return;
    e.preventDefault();
    zone.classList.remove('dragover');
    const file=e.dataTransfer?.files?.[0];
    if(file) processLabImport(file);
  });
}

function itemIdsUsingField(key){
  const usesKey = it => it.fields?.some(f => f.key === key);
  return [
    ...CHECKLIST1.filter(usesKey).map(it => 't1:' + it.id),
    ...PHASES.flatMap(p => p.roles.flatMap(r => r.items)).filter(usesKey).map(it => it.pathId)
  ];
}

// Editing data invalidates prior confirmations everywhere the data is used.
function invalidateConfirmations(itemIds){
  itemIds.forEach(id => {
    delete STATE.checked[id];
    delete ITEM_ERRORS[id];
    const row = document.querySelector(`.item[data-id="${id}"]`);
    if (row){
      row.classList.remove('checked');
      row.querySelector('input[type=checkbox]').checked = false;
      row.querySelector('.item-errors')?.remove();
    }
  });
  PHASES.forEach(p => p.roles.forEach(r => refreshRoleCount(r.id)));
  updateProgress();
}

function refreshRoleCount(roleId){
  const ph = PHASES.find(p => p.roles.some(r=>r.id===roleId));
  if (!ph) return;
  const r = ph.roles.find(rr=>rr.id===roleId);
  if (!r || r.jump) return;
  const block = document.querySelector(`.role-block[data-role="${roleId}"] .role-count`);
  if (block){
    const total = r.items.filter(it=>!it.divider).length;
    const done = r.items.reduce((n,it,idx)=> n + (STATE.checked[it.pathId] ? 1:0), 0);
    block.textContent = `${done}/${total}`;
  }
  const phaseHead = document.querySelectorAll('.phase-head .phase-progress');
  const idx = PHASES.findIndex(p=>p.id===ph.id);
  if (phaseHead[idx]){
    const totalItems = ph.roles.reduce((n,rr)=> n + rr.items.filter(it=>!it.divider).length, 0);
    const doneItems = ph.roles.reduce((n,rr)=> n + rr.items.reduce((m,it,i2)=> m + (STATE.checked[it.pathId]?1:0),0), 0);
    phaseHead[idx].textContent = `${doneItems}/${totalItems}`;
  }
}

// Sections are missing when the case's Eingriffsart excludes all their items.
function hideMissingRailTargets(){
  document.querySelectorAll('[data-rail-target]').forEach(btn => {
    btn.hidden = !document.querySelector(btn.dataset.railTarget);
  });
}

function switchTab(tab){
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab===tab));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-'+tab).classList.add('active');
}

function updateProgress(){
  renderProgress(preopItemIds(), 'preopPct', 'preopSegbar');
  renderProgress(pathItemIds(), 'pathPct', 'pathSegbar');
}

function renderProgress(ids, pctId, segId){
  const total = ids.length;
  const done = ids.filter(id => STATE.checked[id]).length;
  const pct = total ? Math.round((done/total)*100) : 0;
  // A section without items for this Eingriffsart has nothing to do, not 0 % done.
  document.getElementById(pctId).textContent = total ? pct + '%' : '–';
  const segCount = 20;
  const filled = Math.round((pct/100)*segCount);
  const seg = document.getElementById(segId);
  seg.innerHTML = Array.from({length:segCount}).map((_,i)=> `<div class="seg ${i<filled?'filled':''}"></div>`).join("");
}

// Shows the last server result; nothing here decides anything itself.
function renderDerived(){
  updateQuestionnaireResults();
  const bmi = document.getElementById('bmi');
  if (bmi) bmi.textContent = DERIVED.bmi != null ? DERIVED.bmi.toFixed(1) + ' kg/m²' : 'Grösse und Gewicht erfassen';
  document.querySelectorAll('.flag-box[data-rule]').forEach(el => {
    const text = DERIVED.flagMessages?.[el.dataset.rule];
    el.textContent = text || '';
    el.classList.toggle('show', !!text);
  });
  const flagged = new Set(DERIVED.flaggedFields || []);
  const refused = new Set(Object.values(ITEM_ERRORS).flatMap(Object.keys));
  document.querySelectorAll('[data-fkey]').forEach(field => {
    const key = field.dataset.fkey;
    if (document.activeElement !== field) field.value = STATE.answers[key] ?? '';
    const filled = !!field.value;
    // checkValidity only applies the field's own min/max/step from the definition.
    const invalid = refused.has(key) || (filled && !field.checkValidity());
    field.classList.toggle('invalid', invalid || (filled && flagged.has(key)));
    field.classList.toggle('valid', filled && !invalid && !flagged.has(key));
    field.setAttribute('aria-invalid', String(invalid));
  });
  renderWorklist();
}

function scheduleSave(){
  clearTimeout(saveTimer);
  document.getElementById('saveState').textContent = 'speichere …';
  saveTimer = setTimeout(() => { saveTimer = null; saveState(false); }, 500);
}

// Ticks are saved at once, so the server's verdict follows without delay.
function saveNow(){
  clearTimeout(saveTimer);
  saveTimer = null;
  document.getElementById('saveState').textContent = 'speichere …';
  saveState();
}

/* ============================= LIVE SYNC ============================= */
// Several workstations may edit the same case at the same time. Each save
// carries the server revision it is based on (409 on conflict), and every
// open checklist polls the revision. Newer server states are merged into the
// local state field by field: remote changes are shown immediately, local
// edits that are not saved yet are kept and saved afterwards.
const SYNC_POLL_MS = 3000;
const SYNC = { revision:null, base:null, saving:false, resave:false, polling:false };
// UI preferences per workstation; never taken over from other clients.
const LOCAL_ONLY_KEYS = ['openBlocks'];

function emptyState(){
  return { patientName:"", opDate:"", checked:{}, openBlocks:{}, answers:{}, notes:{}, labs:[], suchtmittel:[] };
}

function cloneValue(value){
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function isPlainObject(value){
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function deepEqual(a, b){
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v,i) => deepEqual(v, b[i]));
  if (isPlainObject(a) && isPlainObject(b)){
    const keys = Object.keys(a);
    return keys.length === Object.keys(b).length && keys.every(k => Object.prototype.hasOwnProperty.call(b, k) && deepEqual(a[k], b[k]));
  }
  return false;
}

// Three-way merge. Lists (labs, suchtmittel) are treated as one value; if the
// same value was changed locally and remotely, the local (newer) edit wins.
function mergeStates(base, local, remote){
  if (deepEqual(local, base)) return cloneValue(remote);
  if (deepEqual(remote, base)) return cloneValue(local);
  if (isPlainObject(local) && isPlainObject(remote)){
    const b = isPlainObject(base) ? base : {};
    const out = {};
    new Set([...Object.keys(local), ...Object.keys(remote)]).forEach(k => {
      const value = mergeStates(b[k], local[k], remote[k]);
      if (value !== undefined) out[k] = value;
    });
    return out;
  }
  return cloneValue(local);
}

function withoutLocalOnly(state){
  const copy = Object.assign({}, state);
  LOCAL_ONLY_KEYS.forEach(k => delete copy[k]);
  return copy;
}

function serverState(res){
  return Object.assign(emptyState(), JSON.parse(res.value));
}

// Takes over a server response: its state (merged with edits made meanwhile),
// the derived results and the reasons for refused ticks.
function applyServerResult(res, base){
  const remote = serverState(res);
  DERIVED = res.derived || {};
  const refused = res.validationErrors || {};
  Object.assign(ITEM_ERRORS, refused);
  const changed = adoptRemoteState(base || remote, remote);
  Object.keys(ITEM_ERRORS).forEach(id => { if (STATE.checked[id]) delete ITEM_ERRORS[id]; });
  if (!changed){
    if (Object.keys(refused).length) rerenderFromState(); else renderDerived();
  }
  return { remote, changed };
}

function captureUIState(){
  const ui = { focus:null, notes:[], referrals:[] };
  const el = document.activeElement;
  if (el && el !== document.body){
    const attrs = ['data-fkey','data-notekey','data-lab-idx','data-lab-key','data-sucht-idx','data-sucht-key','data-referral','data-property'];
    const selector = el.id ? '#'+CSS.escape(el.id)
      : attrs.filter(a => el.hasAttribute(a)).map(a => `[${a}="${CSS.escape(el.getAttribute(a))}"]`).join('');
    if (selector){
      ui.focus = { selector, index:[...document.querySelectorAll(selector)].indexOf(el) };
      try{ ui.focus.start = el.selectionStart; ui.focus.end = el.selectionEnd; }catch(_){ /* not a text field */ }
    }
  }
  document.querySelectorAll('.note-wrap.open[data-notewrap]').forEach(w => ui.notes.push(w.dataset.notewrap));
  document.querySelectorAll('details.referral').forEach((d,i) => { if (d.open) ui.referrals.push(i); });
  ui.scrollY = window.scrollY;
  return ui;
}

function restoreUIState(ui){
  ui.notes.forEach(id => {
    const wrap = document.querySelector(`[data-notewrap="${CSS.escape(id)}"]`);
    if (!wrap) return;
    wrap.classList.add('open');
    const toggle = document.querySelector(`[data-notetoggle="${CSS.escape(id)}"]`);
    if (toggle) toggle.textContent = '– Notiz ausblenden';
  });
  const referrals = document.querySelectorAll('details.referral');
  ui.referrals.forEach(i => { if (referrals[i]) referrals[i].open = true; });
  if (ui.focus){
    const matches = document.querySelectorAll(ui.focus.selector);
    const el = matches[ui.focus.index] || matches[0];
    if (el){
      el.focus({preventScroll:true});
      if (ui.focus.start != null){
        try{ el.setSelectionRange(ui.focus.start, ui.focus.end); }catch(_){ /* not a text field */ }
      }
    }
  }
  window.scrollTo(window.scrollX, ui.scrollY);
}

function rerenderFromState(){
  const ui = captureUIState();
  const pname = document.getElementById('pname');
  const opdate = document.getElementById('opdate');
  if (document.activeElement !== pname) pname.value = STATE.patientName || "";
  if (document.activeElement !== opdate) opdate.value = STATE.opDate || "";
  renderChecklist1();
  renderPhases();
  updateProgress();
  renderDerived();
  restoreUIState(ui);
}

// Merges a (normalized) server state into STATE and re-renders if needed.
function adoptRemoteState(base, remote){
  const merged = mergeStates(base, STATE, remote);
  LOCAL_ONLY_KEYS.forEach(k => { merged[k] = STATE[k]; });
  const changed = !deepEqual(merged, STATE);
  if (changed){
    STATE = Object.assign(emptyState(), merged);
    rerenderFromState();
  }
  return changed;
}

async function pullRemoteState(force){
  const res = await window.storage.get(caseStorageKey(), false);
  // A save finished meanwhile and already delivered a newer state.
  if (!force && (SYNC.saving || (SYNC.revision != null && res.revision <= SYNC.revision))) return { changed:false, localEdits:false };
  const { remote, changed } = applyServerResult(res, SYNC.base);
  SYNC.base = remote;
  SYNC.revision = res.revision;
  return { changed, localEdits:!deepEqual(withoutLocalOnly(STATE), withoutLocalOnly(remote)) };
}

function syncTime(){
  return new Date().toLocaleTimeString('de-CH',{hour:'2-digit',minute:'2-digit'});
}

async function pollRemoteState(){
  if (SYNC.polling || SYNC.saving || saveTimer || document.hidden || SYNC.revision == null || !currentCaseNumber()) return;
  SYNC.polling = true;
  try{
    const res = await window.erasApi.fetch(`/api/cases/${encodeURIComponent(currentCaseNumber())}/state/revision/`);
    if (res.revision === SYNC.revision || SYNC.saving || saveTimer) return;
    const { changed, localEdits } = await pullRemoteState(false);
    if (changed) document.getElementById('saveState').textContent = 'Aktualisiert (Änderung von anderem Arbeitsplatz) · ' + syncTime();
    if (localEdits) scheduleSave();
  }catch(err){
    console.warn('Live-Aktualisierung fehlgeschlagen', err);
  }finally{
    SYNC.polling = false;
  }
}

function startLiveSync(){
  setInterval(pollRemoteState, SYNC_POLL_MS);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) pollRemoteState(); });
}

async function saveState(){
  if (SYNC.saving){ SYNC.resave = true; return; }
  SYNC.saving = true;
  const sent = cloneValue(STATE);
  try{
    const res = await window.storage.set(caseStorageKey(), JSON.stringify(sent), {baseRevision: SYNC.revision ?? undefined});
    // Takes over server-side normalization (scores, invalid ticks removed)
    // for everything not edited again while the request was running.
    const { remote } = applyServerResult(res, sent);
    SYNC.base = remote;
    SYNC.revision = res.revision;
    document.getElementById('saveState').textContent = 'Automatisch gespeichert · ' + syncTime();
  }catch(err){
    if (err.status === 409){
      try{
        const { localEdits } = await pullRemoteState(true);
        SYNC.resave = SYNC.resave || localEdits;
        document.getElementById('saveState').textContent = 'Mit Änderungen eines anderen Arbeitsplatzes zusammengeführt · ' + syncTime();
      }catch(pullErr){
        document.getElementById('saveState').textContent = 'Speichern fehlgeschlagen — bitte Eingaben notieren';
        console.error('Storage error', pullErr);
      }
    }else{
      document.getElementById('saveState').textContent = 'Speichern fehlgeschlagen — bitte Eingaben notieren';
      console.error('Storage error', err);
    }
  }finally{
    SYNC.saving = false;
    if (SYNC.resave){
      SYNC.resave = false;
      saveState();
    }
  }
}

async function loadState(){
  try{
    const res = await window.storage.get(caseStorageKey(), false);
    if (res && res.value){
      STATE = serverState(res);
      SYNC.base = cloneValue(STATE);
      SYNC.revision = res.revision;
      DERIVED = res.derived || {};
      ITEM_ERRORS = res.validationErrors || {};
    }
  }catch(err){
    // no saved state yet — start fresh
  }
  const params = new URLSearchParams(window.location.search);
  const patient = params.get("patient");
  const caseNumber = params.get("case");
  const opDate = params.get("opdate");
  if (!STATE.patientName && (patient || caseNumber)){
    STATE.patientName = [patient, caseNumber ? `Fall ${caseNumber}` : ""].filter(Boolean).join(" · ");
  }
  if (opDate && !STATE.opDate){
    STATE.opDate = opDate;
  }
  document.getElementById('pname').value = STATE.patientName || "";
  document.getElementById('opdate').value = STATE.opDate || "";
  renderChecklist1();
  renderPhases();
  hideMissingRailTargets();
  updateProgress();
  renderDerived();
  document.getElementById('saveState').textContent = 'Bereit';
  startLiveSync();
}

function caseStorageKey(){
  const caseId = new URLSearchParams(location.search).get('case');
  return caseId ? `bene-eras-case:${caseId}` : 'bene-eras-state-v3';
}

// Deferred scripts have all run by now, so every part of the page is defined.
document.addEventListener('DOMContentLoaded', () => {
  attachHandlers();
  loadState();
});
