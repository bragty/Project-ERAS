/* Interactive transcription of the forms embedded in Checkliste BENE20052026.docx. */
const scoreOption = (value,label) => ({value:String(value),label:`${value} – ${label}`});
const question = (key,label,options) => ({key,label,type:'select',options:options.map(([value,text])=>scoreOption(value,text))});
const G8_QUESTIONS = [
  question('g8_food','Hat die Nahrungsaufnahme in den letzten 3 Monaten wegen Appetitverlust, Verdauungsproblemen, Kau- oder Schluckstörungen abgenommen?',[[0,'Schwere Einschränkung der Nahrungsaufnahme'],[1,'Mässige Einschränkung der Nahrungsaufnahme'],[2,'Normale Nahrungsaufnahme']]),
  question('g8_weight','Gewichtsverlust in den letzten 3 Monaten?',[[0,'Gewichtsverlust >3 kg'],[1,'Unbekannt'],[2,'Gewichtsverlust zwischen 1 und 3 kg'],[3,'Kein Gewichtsverlust']]),
  question('g8_mobility','Mobilität',[[0,'Bett oder Stuhl'],[1,'Kann aus Bett/Stuhl aufstehen, geht aber nicht nach draussen'],[2,'Geht nach draussen']]),
  question('g8_neuro','Neuropsychologische Probleme?',[[0,'Schwere Demenz oder Depression'],[1,'Milde Demenz oder Depression'],[2,'Keine psychischen Probleme']]),
  question('g8_bmi','Body-Mass-Index (Gewicht in kg / Grösse in m²)',[[0,'BMI <19'],[1,'BMI 19 bis unter 21'],[2,'BMI 21 bis unter 23'],[3,'BMI ≥23']]),
  question('g8_medication','Nimmt mehr als 3 Medikamente pro Tag ein?',[[0,'Ja'],[1,'Nein']]),
  question('g8_health','Verglichen mit Gleichaltrigen: Wie schätzt der Patient seinen Zustand ein?',[[0,'Nicht so gut'],[0.5,'Weiss nicht'],[1,'Gleich gut'],[2,'Besser']]),
  question('g8_age','Alter',[[0,'Über 85 Jahre'],[1,'80 bis 85 Jahre'],[2,'Unter 80 Jahre']])
];
const STOPBANG_QUESTIONS = [
  ['snoring','Schnarchen Sie laut (lauter als Sprechen oder hörbar durch eine geschlossene Tür)?'],
  ['tired','Fühlen Sie sich häufig müde oder schläfrig tagsüber?'],
  ['observed','Hat jemand beobachtet, dass Sie im Schlaf aufhören zu atmen?'],
  ['pressure','Werden Sie oder wurden Sie wegen hohen Blutdrucks behandelt?'],
  ['bmi','BMI höher als 35 kg/m²?'],
  ['age','Älter als 50 Jahre?'],
  ['neck','Halsumfang grösser als 40 cm (bei Frauen) bzw. 43 cm (bei Männern)?'],
  ['sex','Männlich?']
].map(([key,label])=>question('stopbang_'+key,label,[[1,'Ja'],[0,'Nein']]));
const EPWORTH_QUESTIONS = ['Beim Sitzen oder Lesen','Vor dem Fernseher','Im Kino oder Theater','Als Beifahrer im Auto','Beim Hinlegen mittags','Im Gespräch','Im Sitzen nach dem Essen','Im Auto vor dem Rotlicht']
  .map((label,index)=>question('epworth_'+index,label,[[0,'Würde niemals einnicken'],[1,'Geringe Wahrscheinlichkeit einzunicken'],[2,'Mittlere Wahrscheinlichkeit einzunicken'],[3,'Hohe Wahrscheinlichkeit einzunicken']]));
const QUESTIONNAIRES = {
  'fb-g8':{key:'score_g8',max:17,questions:G8_QUESTIONS},
  'fb-stopbang':{key:'score_stopbang',max:8,questions:STOPBANG_QUESTIONS},
  'fb-epworth':{key:'score_epworth',max:24,questions:EPWORTH_QUESTIONS}
};
Object.entries(QUESTIONNAIRES).forEach(([id,config])=>{
  const item=CHECKLIST1.find(it=>it.id===id);
  item.fields=[...config.questions,{...item.fields[0],readonly:true,step:id==='fb-g8'?'0.5':'1',label:`Gesamtpunktzahl (automatisch, 0–${config.max})`},...item.fields.slice(1)];
});
CHECKLIST1.find(it=>it.id==='fb-epworth').detail=[
  'Wie leicht fällt es Ihnen, in den folgenden Situationen einzuschlafen? Gemeint ist das Gefühl der Schläfrigkeit, nicht nur Müdigkeit. Beziehen Sie sich auf das übliche tägliche Leben der vergangenen Wochen. Falls eine Situation zuletzt nicht vorkam, stellen Sie sich deren Wirkung vor.',
  'Jede Situation mit 0 bis 3 bewerten. Auffällig ab einer Gesamtpunktzahl von 11.'
];
CHECKLIST1.find(it=>it.id==='fb-stopbang').detail=['Jede Frage mit Ja oder Nein beantworten. Ab 3 Ja-Antworten ist gemäss BENE-Checkliste die Zuweisung zur OSAS-Abklärung erforderlich.'];
CHECKLIST1.find(it=>it.id==='fb-ecog').fields[0].options=[
  scoreOption(0,'Keine Beschwerden, keine Zeichen der Krankheit; normale Aktivität ohne oder mit geringen Symptomen'),
  scoreOption(1,'Normale Aktivität mit Anstrengung möglich; deutliche Symptome; selbständig, aber keine normale Aktivität oder Arbeit'),
  scoreOption(2,'Einige Hilfestellung nötig; grösstenteils selbständig; Hilfe und medizinische Versorgung werden oft in Anspruch genommen'),
  scoreOption(3,'Behindert; qualifizierte Hilfe benötigt; schwerbehindert, Hospitalisation erforderlich'),
  scoreOption(4,'Schwerkrank; intensive medizinische Massnahmen erforderlich; moribund, unaufhaltsamer Verlauf'),
  scoreOption(5,'Verstorben')
];
CHECKLIST1.find(it=>it.id==='fb-mmrc').fields[0].options=[
  scoreOption(0,'Atemnot nur bei starker Anstrengung'),
  scoreOption(1,'Atemnot beim schnellen Gehen oder beim Bergaufgehen mit leichter Steigung'),
  scoreOption(2,'Langsameres Gehen als Gleichaltrige in der Ebene wegen Atemnot oder notwendige Pausen bei selbstgewählter Geschwindigkeit'),
  scoreOption(3,'Pause wegen Atemnot beim Gehen in der Ebene nach knapp 100 m oder nach einigen Minuten notwendig'),
  scoreOption(4,'Zu kurzatmig, um das Haus zu verlassen, oder Atemnot beim An- und Ausziehen')
];
CHECKLIST1.find(it=>it.id==='fb-nrs').detail=['Die bereitgestellte Checkliste enthält keinen vollständigen NRS-Fragebogen. Den extern erhobenen NRS-Gesamtwert hier erfassen.'];
CHECKLIST1.filter(it=>it.id?.startsWith('fb-')).forEach(it=>it.questionnaire=true);
['fb-ecog','fb-mmrc'].forEach(id=>{
  const item=CHECKLIST1.find(it=>it.id===id);
  item.detail ||= [];
  item.detail.push(`<p class="questionnaire-description" data-score-description="${id}" aria-live="polite"></p>`);
});

function questionnaireScore(config,answers){
  const values=config.questions.map(q=>answers[q.key]);
  if(values.some((value,index)=>value==null || value==='' || !config.questions[index].options.some(o=>o.value===String(value)))) return null;
  return values.reduce((sum,value)=>sum+Number(value),0);
}
function updateQuestionnaireResults(){
  CHECKLIST1.filter(it=>it.questionnaire).forEach(item=>{
    const config=QUESTIONNAIRES[item.id];
    const key=config?.key||item.fields[0].key;
    const value=STATE.answers[key];
    const output=document.querySelector(`[data-questionnaire-result="${item.id}"]`);
    if(!output) return;
    const answered=config ? config.questions.filter(q=>STATE.answers[q.key]!=null&&STATE.answers[q.key]!=='').length : 0;
    const legacy=STATE.legacyScores?.[key];
    output.textContent=config ? (answered===config.questions.length ? ` · ${value} / ${config.max} Punkte` : ` · ${answered} / ${config.questions.length} beantwortet${legacy!=null ? ` · Bisheriger Gesamtwert: ${legacy}`:''}`) : (value!=null && value!=='' ? ` · Wert: ${value}` : ' · Noch offen');
    const description=document.querySelector(`[data-score-description="${item.id}"]`);
    if(description) description.textContent=item.fields[0].options.find(o=>o.value===String(value))?.label||'Bitte einen Grad auswählen.';
  });
}
function migrateQuestionnaireState(){
  Object.entries(QUESTIONNAIRES).forEach(([id,config])=>{
    const score=questionnaireScore(config,STATE.answers);
    if(score===null){
      if(STATE.answers[config.key]!=null && STATE.answers[config.key]!==''){
        STATE.legacyScores ||= {};
        STATE.legacyScores[config.key]=STATE.answers[config.key];
      }
      STATE.answers[config.key]='';
      delete STATE.checked['t1:'+id];
    }else STATE.answers[config.key]=String(score);
  });
  // Older ECOG selections used a combined number/description as the saved value.
  const ecog=STATE.answers.score_ecog;
  if(typeof ecog==='string' && /^[0-5] = /.test(ecog)) STATE.answers.score_ecog=ecog[0];
}
document.body.addEventListener('input',e=>{
  const key=e.target.dataset.fkey;
  const match=Object.entries(QUESTIONNAIRES).find(([,config])=>config.questions.some(q=>q.key===key));
  if(!match) return;
  const [id,config]=match;
  STATE.answers[key]=e.target.value;
  const score=questionnaireScore(config,STATE.answers);
  STATE.answers[config.key]=score===null?'':String(score);
  delete STATE.checked['t1:'+id];
});
document.body.addEventListener('toggle',e=>{
  const id=e.target.dataset.questionnaire;
  if(!id) return;
  STATE.openBlocks['questionnaire:'+id]=e.target.open;
  scheduleSave();
},true);
