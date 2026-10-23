/* Zuweisungen und Arbeitsliste. Which referral is indicated and its KISIM text
   come from the backend (apps/checklist/rules.py, DERIVED.referrals); this file
   renders them and keeps status and date the user documents. */
const REFERRAL_STATUSES=['Noch zu prüfen','Nicht erforderlich','Zuweisung erforderlich','Zuweisung erfolgt','Termin / Datum ausstehend','Zuweisung abgeschlossen'];
let renderedWorklist='';

function referralById(id){
  return (DERIVED.referrals||[]).find(r=>r.id===id);
}
function referralStatus(referral){
  return STATE.referrals[referral.id]?.status || (referral.required?'Zuweisung erforderlich':'Noch zu prüfen');
}
function referralSummary(referral){
  return `${esc(referral.label)} · ${esc(referralStatus(referral))}${referral.required?' · Indikation erfasst':''}`;
}
function renderWorklist(){
  const el=document.getElementById('worklist'); if(!el) return;
  STATE.referrals ||= {};
  const referrals=DERIVED.referrals||[];
  // Re-render only on changes, so open entries and focus are not lost on every save.
  const signature=JSON.stringify([referrals,STATE.referrals,referrals.map(r=>r.dateField && STATE.answers[r.dateField])]);
  if(signature===renderedWorklist) return;
  renderedWorklist=signature;
  const open=new Set([...el.querySelectorAll('details.referral[open]')].map(d=>d.dataset.referralId));
  el.innerHTML='<h2>Zuweisungen und Arbeitsliste</h2><p>Status und Termine separat dokumentieren. Text vor Übernahme in KISIM prüfen.</p>'+referrals.map(referral=>{
    const date=referral.dateField ? STATE.answers[referral.dateField] : STATE.referrals[referral.id]?.date;
    return `<details class="referral" data-referral-id="${referral.id}" ${open.has(referral.id)?'open':''}><summary>${referralSummary(referral)}</summary>
      <label>Status <select data-referral="${referral.id}" data-property="status">${optionsHTML(REFERRAL_STATUSES,referralStatus(referral))}</select></label>
      <label>Termin <input type="date" data-referral="${referral.id}" data-property="date" value="${esc(date||'')}"></label>
      <textarea rows="5" readonly aria-label="Textbaustein ${esc(referral.label)}">${esc(referral.text)}</textarea><button type="button" class="btn" data-copy-referral="${referral.id}">Text kopieren</button></details>`;
  }).join('');
}
document.body.addEventListener('change',e=>{
  const f=e.target;
  if(!f.dataset.referral) return;
  const referral=referralById(f.dataset.referral);
  STATE.referrals[f.dataset.referral] ||= {};
  STATE.referrals[f.dataset.referral][f.dataset.property]=f.value;
  // A referral date that is also a checklist field is entered through that field.
  if(f.dataset.property==='date' && referral?.dateField){
    STATE.answers[referral.dateField]=f.value;
    document.querySelectorAll(`[data-fkey="${referral.dateField}"]`).forEach(field=>{field.value=f.value;field.dispatchEvent(new Event('input',{bubbles:true}));});
    return;
  }
  if(referral) f.closest('details').querySelector('summary').innerHTML=referralSummary(referral);
  scheduleSave();
});
document.body.addEventListener('click',async e=>{
  const button=e.target.closest('[data-copy-referral]'); if(!button) return;
  try{await navigator.clipboard.writeText(referralById(button.dataset.copyReferral)?.text||'');button.textContent='Kopiert';}
  catch{button.closest('details').querySelector('textarea').select();button.textContent='Bitte mit Strg+C kopieren';}
});
