const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
// Rules (scores, flags, required fields, referrals, migrations) are tested in
// Python (apps/checklist/tests_rules.py); here only what the frontend does itself.
function app(){
  const definition=fs.readFileSync(path.join(__dirname,'../apps/checklist/definition.json'),'utf8');
  const context=vm.createContext({document:{addEventListener(){},body:{addEventListener(){}},getElementById(id){return id==='checklist-definition'?{textContent:definition}:{addEventListener(){}};}},location:{search:'?case=A'},URLSearchParams,Date});
  for(const file of ['checklist','questionnaires','worklist']) vm.runInContext(fs.readFileSync(path.join(__dirname,`static/eras/js/${file}.js`),'utf8'),context);
  return expression=>vm.runInContext(expression,context);
}
test('removed items do not shift saved pathway identities; all measures have unique IDs',()=>{
  const run=app();
  assert.equal(run("CHECKLIST1.find(item=>item.id==='kisimpfad')"),undefined);
  assert.equal(run("PHASES[0].roles[0].items[2].pathId"),'t2:p-uro:3');
  assert.equal(run('new Set(allItemIds()).size === allItemIds().length'),true);
  assert.equal(run("JSON.stringify(PHASES).includes('Instruktion Fragmin')"),false);
  assert.equal(run("PHASES.find(p=>p.id==='postop-stat').roles[0].items[0].divider"),'OP-Tag');
});
test('fields keep zero values',()=>{
  const run=app();
  assert.equal(run("fieldsHTML([{key:'zero',label:'Zero',type:'number'}])").includes('value=""'),true);
  run('STATE.answers.zero=0');
  assert.ok(run("fieldsHTML([{key:'zero',label:'Zero',type:'number'}])").includes('value="0"'));
});
test('case isolation of the storage key',()=>{
  const run=app();
  assert.equal(run('caseStorageKey()'),'bene-eras-case:A');
  run("location.search='?case=B'");
  assert.equal(run('caseStorageKey()'),'bene-eras-case:B');
});
test('reasons for a refused tick are shown with field labels',()=>{
  const run=app();
  run("ITEM_ERRORS['t1:raucher']={raucher_py:'Pflichtfeld.',labs:'Mindestens einen Laborwert erfassen.'}");
  const html=run("itemErrorsHTML('t1:raucher',[{key:'raucher_py',label:'Pack Years'}])");
  assert.match(html,/Pack Years: Pflichtfeld\./);
  assert.match(html,/Mindestens einen Laborwert erfassen\./);
  assert.equal(run("itemErrorsHTML('t1:pbm',[])"),'');
});
test('questionnaire progress and server total are displayed',()=>{
  const run=app();
  const config="QUESTIONNAIRES['fb-stopbang']";
  assert.equal(run(`questionnaireResultText(${config},'',undefined)`),' · 0 / 8 beantwortet');
  assert.equal(run(`questionnaireResultText(${config},'',12)`),' · 0 / 8 beantwortet · Bisheriger Gesamtwert: 12');
  run(`${config}.questions.forEach(q=>STATE.answers[q.key]='1')`);
  run("DERIVED.patientSex='male'");
  assert.equal(run(`questionnaireResultText(${config},'',undefined)`),' · wird berechnet …');
  assert.equal(run(`questionnaireResultText(${config},'8',undefined)`),' · 8 / 8 Punkte');
});
test('a section without items shows a dash instead of 0 %',()=>{
  const run=app();
  run("var shown={};document.getElementById=id=>shown[id]||(shown[id]={textContent:'',innerHTML:''})");
  run("renderProgress([],'pct','seg')");
  assert.equal(run("shown.pct.textContent"),'–');
  run("STATE.checked={'t1:pbm':true}; renderProgress(['t1:pbm','t1:kardio'],'pct','seg')");
  assert.equal(run("shown.pct.textContent"),'50%');
});

test('optional male fields use central patient data and preserve hidden values',()=>{
  const run=app();
  const fields="CHECKLIST1.find(it=>it.id==='untersuchung').fields";
  run("STATE.answers.untersuchung_prostata='35.5'");
  assert.match(run(`fieldsHTML(${fields})`), /data-male-field hidden/);
  assert.match(run(`fieldsHTML(${fields})`), /value="35.5"/);
  run("DERIVED.patientSex='male'");
  assert.doesNotMatch(run(`fieldsHTML(${fields})`), /data-male-field hidden/);
  assert.match(run(`fieldsHTML(${fields})`), /Prostatavolumen \(ml\) \(optional\)/);
  assert.ok(run("itemIdsUsingField('stopbang_sex').includes('t1:fb-stopbang')"));
});

test('legacy questionnaire sex never determines field visibility',()=>{
  const run=app();
  run("STATE.answers.stopbang_sex='1'; DERIVED.patientSex=''");
  assert.equal(run('isMalePatient()'),false);
  assert.equal(run('patientSexAnswer()'),'');
  const html=run("fieldsHTML(resolveFields(['stopbang_sex']))");
  assert.match(html,/Stammdaten nachpflegen/);
  assert.doesNotMatch(html,/<select/);
  run("DERIVED.patientSex='female'");
  assert.equal(run('patientSexAnswer()'),'0');
});

test('numeric drafts retain invalid text and use shared ranges and steps',()=>{
  const run=app();
  run("STATE.answers.vital_gewicht='abc'");
  assert.match(run("fieldsHTML(resolveFields(['vital_gewicht']))"),/type="text" inputmode="decimal".*value="abc"/);
  for(const [key,value,expected] of [
    ['vital_gewicht','abc','Zahlenwert'],['vital_gewicht','-1','mindestens 0'],
    ['vital_temp','37.05','Schritten'],['vital_spo2','101','höchstens 100'],
    ['score_nrs','1.5','Schritten'],['vital_gewicht','300.5','']
  ]){
    const message=run(`checklistFieldMessage({dataset:{fkey:${JSON.stringify(key)}},value:${JSON.stringify(value)},validity:{}})`);
    assert.ok(expected?message.includes(expected):message==='',`${key}: ${message}`);
  }
});

test('date validation rejects impossible calendar dates without assuming a surgical timeline',()=>{
  const run=app();
  for(const date of ['2026-02-30','20261101','0000-01-01','2026-13-01']) assert.equal(run(`validISODate(${JSON.stringify(date)})`),false);
  for(const date of ['2024-02-29','2026-11-01','2030-01-01']) assert.equal(run(`validISODate(${JSON.stringify(date)})`),true);
  assert.equal(run("operationDateMessage('01.11.2026')"),'');
  assert.match(run("operationDateMessage('31.02.2026')"),/gültiges OP-Datum/);
});

test('structured clinical controls restore values and escape free text',()=>{
  const run=app();
  run(`STATE.answers.anamnese_aerzte=[{specialty:'<script>',name:'QA'}];
       STATE.answers.stuhl_rezept='Ja';
       STATE.answers.kardio_risiken=[CHECKLIST_DEFINITION.fields.kardio_risiken.options[0]]`);
  assert.match(run("physiciansHTML('anamnese_aerzte')"), /&lt;script&gt;/);
  assert.match(run("fieldsHTML(resolveFields(['stuhl_rezept']))"), /data-checkbox-key="stuhl_rezept" checked/);
  const html=run("fieldsHTML(resolveFields(['kardio_risiken']))");
  assert.equal((html.match(/checked/g)||[]).length,1);
  assert.equal((html.match(/type="checkbox"/g)||[]).length,5);
});

test('clinical draft errors appear at the affected field',()=>{
  const run=app();
  run("ITEM_ERRORS['t1:untersuchung']={untersuchung_hals:'Wert muss mindestens 0 sein.'}");
  assert.match(run("fieldsHTML(resolveFields(['untersuchung_hals']))"), /field-error.*Wert muss mindestens 0 sein\./);
});
