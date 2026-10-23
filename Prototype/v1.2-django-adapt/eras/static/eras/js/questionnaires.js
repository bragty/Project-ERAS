/* Interactive transcription of the forms embedded in Checkliste BENE20052026.docx.
   Questions, options and texts are part of the checklist definition; scored
   questionnaires carry a "scoring" entry there. The total is computed by the
   backend on every save; this file only displays progress and result. */
const QUESTIONNAIRES = Object.fromEntries(CHECKLIST1.filter(it=>it.scoring).map(it=>[it.id,{
  key:it.scoring.scoreKey,
  max:it.scoring.max,
  questions:it.scoring.questions.map(key=>it.fields.find(f=>f.key===key))
}]));

function questionnaireResultText(config,value,legacy){
  if(!config) return value!=null && value!=='' ? ` · Wert: ${value}` : ' · Noch offen';
  const answered=config.questions.filter(q=>STATE.answers[q.key]!=null&&STATE.answers[q.key]!=='').length;
  if(answered<config.questions.length) return ` · ${answered} / ${config.questions.length} beantwortet${legacy!=null ? ` · Bisheriger Gesamtwert: ${legacy}`:''}`;
  return value!=null && value!=='' ? ` · ${value} / ${config.max} Punkte` : ' · wird berechnet …';
}
function updateQuestionnaireResults(){
  CHECKLIST1.filter(it=>it.questionnaire).forEach(item=>{
    const config=QUESTIONNAIRES[item.id];
    const key=config?.key||item.fields[0].key;
    const value=STATE.answers[key];
    const output=document.querySelector(`[data-questionnaire-result="${item.id}"]`);
    if(!output) return;
    output.textContent=questionnaireResultText(config,value,STATE.legacyScores?.[key]);
    const description=document.querySelector(`[data-score-description="${item.id}"]`);
    if(description) description.textContent=item.fields[0].options.find(o=>o.value===String(value))?.label||'Bitte einen Grad auswählen.';
  });
}
document.body.addEventListener('toggle',e=>{
  const id=e.target.dataset.questionnaire;
  if(!id) return;
  STATE.openBlocks['questionnaire:'+id]=e.target.open;
  scheduleSave();
},true);
