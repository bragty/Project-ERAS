/* KSW review 25.09.2026. Original form images remain the source of truth. */
const itemById = id => CHECKLIST1.find(item => item.id === id);
PHASES.forEach(phase => phase.roles.forEach(role => role.items.forEach((item, index) => {
  item.pathId = `t2:${role.id}:${index}`;
})));
CHECKLIST1.splice(CHECKLIST1.findIndex(item => item.id === 'kisimpfad'), 1);
itemById('vitalparameter').fields.push({key:'vital_groesse', label:'Körpergrösse (cm)', type:'number', min:1, step:'0.1'});
itemById('vitalparameter').detail = ['BMI: <output id="bmi">Grösse und Gewicht erfassen</output>'];
itemById('fb-g8').detail = ['Der Grenzwert für eine automatische Geriatrie-Zuweisung muss laut Sitzungsprotokoll fachlich bestätigt werden. Zuweisungsentscheid vorläufig manuell dokumentieren.'];
itemById('kardio').fields[1] = {key:'score_mmrc', label:'mMRC aus Fragebögen', type:'select', options:['0','1','2','3','4']};
FLAG_RULES.kardio = a => (a.kardio_ef !== '' && a.kardio_ef != null && Number(a.kardio_ef)<50) || Number(a.score_mmrc)>=3
  ? 'EF <50% oder mMRC Grad 3/4 → Zuweisung Kardiologie erforderlich.' : null;
itemById('anaesthesie').detail = ['So bald wie möglich, wenn möglich mindestens einen Monat vor Zystektomie und nach allfälligen Kardiologie- und Pneumologieterminen.'];
itemById('pbm').detail[1] = 'Bei perioperativer Immunochemotherapie: PBM durch Onkologie, telefonische Rücksprache mit behandelnder Onkologie (wenn nicht definiert Dr. Gina Treichler). Sonst Hausarzt mit klarem Auftrag gemäss Weisung informieren; falls Eiseninfusion dort nicht möglich: medizinische Poliklinik, Tel. 3751, Stichwort PBM.';
itemById('physio1').detail.push('KISIM: Workflow → neu → Gemeinsame Favoriten → Anmeldung Physiotherapie ambulant ViTA-Reha präoperativ bzw. postoperativ. Operation: Zystektomie mit Anlage Ileum conduit oder orthotope Ersatzblase. Keine Limiten.');
itemById('thromboinfo').detail.push('Gemäss BENE-Checkliste: postoperativ jeder Zystektomie-Patient; präoperativ bei perioperativer Immunchemotherapie Eliquis 2.5 mg 1-0-1 während der Immunchemotherapie. Auf Rezept: 2 Tage vor Operation stoppen.');
itemById('laborwerte').detail = ['Hämatogramm gross; Quick/INR; Ferritin und Transferrinsättigung; Kreatinin, Natrium, Kalium, CRP; Troponin T und BNP.', 'Laborimport/OCR aus KISIM: technische Machbarkeit noch offen. Werte hier manuell erfassen.'];
PHASES[0].roles.find(r=>r.id==='p-uro').items = PHASES[0].roles.find(r=>r.id==='p-uro').items.filter(it=>!it.title.includes('BENE-Nurse informieren'));
const stoma = PHASES[0].roles.find(r=>r.id==='p-stoma');
stoma.items = [stoma.items[0]];
stoma.items[0].title = 'Termin Stomaberatung festlegen';
stoma.items[0].fields = [{key:'stoma_termin',label:'Termin-Datum',type:'date'}];
const sharedFields = {'p-anaes':['anaesthesie'], 'p-physio':['physio1'], 'p-ernaehr':['fb-nrs','ernaehrung1']};
Object.entries(sharedFields).forEach(([roleId,ids])=> {
  const role=PHASES[0].roles.find(r=>r.id===roleId);
  role.items[0].fields=ids.flatMap(id=>itemById(id).fields);
  role.note='Angaben aus der Prä-OP Checkliste werden automatisch übernommen';
});
PHASES[0].roles.find(r=>r.id==='p-ernaehr').items[1].detail[1]='Intervention ab NRS ≥3';
PHASES.find(p=>p.id==='postop-stat').roles.forEach(role=> {
  role.items=role.items.flatMap(it=>it.detail?.length ? [
    {divider:it.title},
    ...it.detail.map((text,index)=>({title:text,pathId:`${it.pathId}:sub:${index}`, ...(index===it.detail.length-1 ? {fields:it.fields,flagRule:it.flagRule}: {})})).filter(child=>!child.title.includes('Instruktion Fragmin'))
  ] : [it]);
});

function caseStorageKey(){
  const caseId=new URLSearchParams(location.search).get('case');
  return caseId ? `bene-eras-case:${caseId}` : 'bene-eras-state-v3';
}
function migrateState(){
  if(STATE.schemaVersion===2) return;
  // A former group tick cannot prove completion of its individual measures.
  PHASES.find(p=>p.id==='postop-stat').roles.forEach(r=>r.items.forEach(it=>{
    if(it.pathId?.includes(':sub:')) delete STATE.checked[it.pathId.split(':sub:')[0]];
  }));
  delete STATE.checked['t2:p-stoma:0'];
  STATE.schemaVersion=2;
}
function saveCaseSummary(){
  const caseId=new URLSearchParams(location.search).get('case');
  if(!caseId) return;
  const ids=allItemIds();
  const summary=JSON.parse(localStorage.getItem('bene-case-summary')||'{}');
  summary[caseId]={...summary[caseId],progress:Math.round(ids.filter(id=>STATE.checked[id]).length/ids.length*100),complete:ids.every(id=>STATE.checked[id])};
  localStorage.setItem('bene-case-summary',JSON.stringify(summary));
}
function getItem(id){
  return id.startsWith('t1:') ? itemById(id.slice(3)) : PHASES.flatMap(p=>p.roles.flatMap(r=>r.items)).find(it=>it.pathId===id);
}
function fieldRequired(key, a){
  if(key.startsWith('sucht_') || key==='pbm_ansprechperson' || key==='thrombo_eGFR') return false;
  if(key==='raucher_sistiert_seit') return a.raucher_status?.startsWith('Ex-');
  if(['raucher_menge','raucher_py'].includes(key)) return a.raucher_status && a.raucher_status!=='Nieraucher' && (key!=='raucher_menge'||a.raucher_status==='Aktiver Raucher');
  if(key.startsWith('pneumo_') && key!=='pneumo_niv' && key!=='pneumo_grunderkrankung') return a.pneumo_grunderkrankung && a.pneumo_grunderkrankung!=='Keine';
  if(key==='ernaehrung_termin') return Number(a.score_nrs)>=3;
  if(key==='operateur_termin_datum') return a.operateur_termin_status==='Ja';
  return true;
}
function validateItem(id){
  const row=document.querySelector(`.item[data-id="${id}"]`);
  let valid=true;
  const disclosure=row.querySelector('details.questionnaire');
  if(disclosure) disclosure.open=true;
  row.querySelectorAll('[data-fkey]').forEach(field=> {
    field.required=!!fieldRequired(field.dataset.fkey,STATE.answers);
    if(!field.checkValidity() || (field.readOnly && field.required && !field.value)){valid=false; field.classList.add('invalid'); field.reportValidity();}
  });
  if(id==='t1:laborwerte' && !STATE.labs.some(l=>l.type && l.value.trim() && l.unit.trim())){
    alert('Mindestens einen Laborwert mit Wert und Einheit erfassen.');valid=false;
  }
  if(id==='t1:laborwerte' && STATE.labs.some(l=>!l.type || !l.value.trim() || !l.unit.trim())){
    valid=false;
  }
  return valid;
}
function updateClinicalUI(){
  updateQuestionnaireResults();
  const a=STATE.answers;
  const height=Number(a.vital_groesse),weight=Number(a.vital_gewicht);
  const bmi=document.getElementById('bmi');
  if(bmi) bmi.textContent=height>0&&weight>0 ? (weight/(height/100)**2).toFixed(1)+' kg/m²' : 'Grösse und Gewicht erfassen';
  document.querySelectorAll('[data-fkey]').forEach(field=>{
    if(document.activeElement!==field) field.value=a[field.dataset.fkey] ?? '';
    const value=field.value;
    const flagged=(['score_stopbang','score_epworth'].includes(field.dataset.fkey)&&FLAG_RULES.pneumo(a)) || (field.dataset.fkey==='score_nrs'&&FLAG_RULES.ernaehrung(a)) || (['score_mmrc','kardio_ef'].includes(field.dataset.fkey)&&FLAG_RULES.kardio(a));
    field.classList.toggle('invalid',!!value&&(!field.checkValidity()||!!flagged));
    field.classList.toggle('valid',!!value&&field.checkValidity()&&!flagged);
    field.setAttribute('aria-invalid',String(!!value&&!field.checkValidity()));
  });
  renderWorklist();
}
const REFERRALS=[['anaesthesie','Anästhesie'],['geriatrie','Geriatrie'],['pbm','PBM'],['kardio','Kardiologie'],['rauchstopp','Rauchstopp'],['osas','Pneumologie OSAS'],['lufu','Pneumologie LuFu'],['ernaehrung','Ernährungsberatung'],['physio','Physiotherapie']];
function referralRequired(id){
  const a=STATE.answers;
  if(['anaesthesie','physio'].includes(id)) return true;
  if(id==='geriatrie') return a.g8_zuweisung==='Ja';
  if(id==='pbm') return a.pbm_status==='Eingeleitet';
  if(id==='kardio') return !!FLAG_RULES.kardio(a);
  if(id==='osas') return !!FLAG_RULES.pneumo(a);
  if(id==='ernaehrung') return !!FLAG_RULES.ernaehrung(a);
  if(id==='rauchstopp') return ['Aktiver Raucher','Ex-Raucher, sistiert <1 Jahr'].includes(a.raucher_status);
  if(id==='lufu'){
    if(a.pneumo_grunderkrankung==='Neuromuskuläre Erkrankung/Tetraplegie') return true;
    if(!a.pneumo_grunderkrankung || a.pneumo_grunderkrankung==='Keine') return false;
    const last=new Date(a.pneumo_letzte_kontrolle);
    const cutoff=new Date();
    cutoff.setMonth(cutoff.getMonth()-(a.pneumo_grunderkrankung==='Lungenfibrose/restriktive Lungenfunktion'?6:12));
    return a.pneumo_verschlechterung==='Ja' || (Number.isFinite(last.getTime()) && last<cutoff);
  }
  return false;
}
function referralText(id){
  const a=STATE.answers;
  const context=`Patient/in: ${STATE.patientName||'[Name ergänzen]'}\nZystektomie geplant am ${STATE.opDate||'[OP-Datum ergänzen]'}.\n`;
  const texts={
    anaesthesie:'Bitte um präoperative Anästhesie-Sprechstunde (PAB), wenn möglich mindestens einen Monat vor Operation und nach kardiologischen/pneumologischen Abklärungen.',
    geriatrie:`Bitte um geriatrische Abklärung. G8-Score: ${a.score_g8??'offen'}. Zuweisungsentscheid manuell dokumentiert: ${a.g8_zuweisung||'offen'}.`,
    pbm:`Bitte um PBM-Optimierung gemäss Weisung „Perioperative Therapie von Anämie und Eisenmangel“. Status: ${a.pbm_status||'offen'}. ${a.pbm_ansprechperson||''}\nLabor: ${STATE.labs.filter(l=>l.value).map(l=>`${l.type}: ${l.value} ${l.unit}`).join(', ')}`,
    kardio:`Bitte um präoperative kardiale Abklärung gemäss Weisung. EF: ${a.kardio_ef??'offen'} %. mMRC: ${a.score_mmrc??'offen'}.`,
    rauchstopp:`Bitte um zeitnahe Anbindung an die Rauchstoppsprechstunde vor Zystektomie. ${a.raucher_status||'Raucherstatus offen'}, ${a.raucher_menge??'offen'} Zigaretten/Tag, kumulativ ${a.raucher_py??'offen'} py. Sistiert seit: ${a.raucher_sistiert_seit||'nicht erfasst'}.`,
    osas:`Bitte um zeitnahe Anbindung für eine OSAS-Abklärung, ggf. Initiierung einer CPAP-Therapie vor Zystektomie. STOP-BANG: ${a.score_stopbang??'offen'}, Epworth: ${a.score_epworth??'offen'}. NIV: ${a.pneumo_niv||'offen'}.`,
    lufu:`Bitte um zeitnahe Anbindung für eine LuFu vor Zystektomie. Grunderkrankung: ${a.pneumo_grunderkrankung||'offen'}, letzte Kontrolle: ${a.pneumo_letzte_kontrolle||'offen'}, Verschlechterung: ${a.pneumo_verschlechterung||'offen'}.`,
    ernaehrung:`Bitte um Aufgebot innert 2 Wochen in die Ernährungsberatung zwecks Abklärung Ernährungszustand und Einleitung allfälliger Optimierungsmassnahmen. NRS: ${a.score_nrs??'offen'}.`,
    physio:`Bitte um Anmeldung ViTA-Reha präoperativ. Operation: ${a.physio_neoblase==='Ja'?'Zystektomie mit Anlage orthotope Ersatzblase':a.physio_neoblase==='Nein'?'Zystektomie mit Anlage Ileum conduit':'Eingriff ergänzen'}. Keine Limiten. ${a.physio_neoblase==='Ja'?'Zusätzlich Beckenbodenphysiotherapie.':''} ${a.physio_rehakur==='Nein'?'Zusätzlich ViTA-Reha postoperativ.':''}`
  };
  return context+texts[id];
}
function renderWorklist(){
  const el=document.getElementById('worklist'); if(!el) return;
  STATE.referrals ||= {};
  el.innerHTML='<h2>Zuweisungen und Arbeitsliste</h2><p>Status und Termine separat dokumentieren. Text vor Übernahme in KISIM prüfen.</p>'+REFERRALS.map(([id,label])=>{
    const entry=STATE.referrals[id]||{};
    const sharedDate={anaesthesie:'anaesthesie_termin',ernaehrung:'ernaehrung_termin'}[id];
    const date=sharedDate ? STATE.answers[sharedDate] : entry.date;
    const status=entry.status|| (referralRequired(id)?'Zuweisung erforderlich':'Noch zu prüfen');
    return `<details class="referral"><summary>${label} · ${esc(status)}${referralRequired(id)?' · Indikation erfasst':''}</summary>
      <label>Status <select data-referral="${id}" data-property="status">${optionsHTML(['Noch zu prüfen','Nicht erforderlich','Zuweisung erforderlich','Zuweisung erfolgt','Termin / Datum ausstehend','Zuweisung abgeschlossen'],status)}</select></label>
      <label>Termin <input type="date" data-referral="${id}" data-property="date" value="${esc(date||'')}"></label>
      <textarea rows="5" readonly aria-label="Textbaustein ${label}">${esc(referralText(id))}</textarea><button type="button" class="btn" data-copy-referral="${id}">Text kopieren</button></details>`;
  }).join('');
}
document.body.addEventListener('change',e=>{
  const f=e.target;
  if(f.dataset.referral){
    STATE.referrals[f.dataset.referral] ||= {};
    STATE.referrals[f.dataset.referral][f.dataset.property]=f.value;
    if(f.dataset.property==='date'){
      const key={anaesthesie:'anaesthesie_termin',ernaehrung:'ernaehrung_termin'}[f.dataset.referral];
      if(key){STATE.answers[key]=f.value;document.querySelectorAll(`[data-fkey="${key}"]`).forEach(field=>{field.value=f.value;field.dispatchEvent(new Event('input',{bubbles:true}));});return;}
    }
    f.closest('details').querySelector('summary').textContent=REFERRALS.find(r=>r[0]===f.dataset.referral)[1]+' · '+(STATE.referrals[f.dataset.referral].status||'Noch zu prüfen');
    scheduleSave();
  }
});
// Editing reused data invalidates prior confirmations everywhere it is used.
document.body.addEventListener('input',e=>{
  const key=e.target.dataset.fkey;
  if(e.target.dataset.labIdx!=null){delete STATE.checked['t1:laborwerte'];updateProgress();scheduleSave();}
  if(!key) return;
  const affected=[...CHECKLIST1.filter(it=>it.fields?.some(f=>f.key===key)).map(it=>'t1:'+it.id),
    ...PHASES.flatMap(p=>p.roles.flatMap(r=>r.items)).filter(it=>it.fields?.some(f=>f.key===key)).map(it=>it.pathId)];
  affected.forEach(id=>{
    delete STATE.checked[id];
    const row=document.querySelector(`.item[data-id="${id}"]`);
    if(row){row.classList.remove('checked');row.querySelector('input[type=checkbox]').checked=false;}
  });
  PHASES.forEach(p=>p.roles.forEach(r=>refreshRoleCount(r.id)));
  updateProgress();scheduleSave();
});
document.body.addEventListener('click',async e=>{
  const button=e.target.closest('[data-copy-referral]'); if(!button) return;
  try{await navigator.clipboard.writeText(referralText(button.dataset.copyReferral));button.textContent='Kopiert';}
  catch{button.closest('details').querySelector('textarea').select();button.textContent='Bitte mit Strg+C kopieren';}
});
['pname','opdate'].forEach(id=>document.getElementById(id).addEventListener('input',()=>renderWorklist()));
attachHandlers();
loadState();
