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
