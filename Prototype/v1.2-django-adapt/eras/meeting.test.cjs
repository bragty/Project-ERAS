const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function app(){
  const context=vm.createContext({document:{body:{addEventListener(){}},getElementById(){return {addEventListener(){}};}},location:{search:'?case=A'},URLSearchParams,Date});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'static/eras/js/checklist.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'static/eras/js/questionnaires.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'static/eras/js/meeting.js'),'utf8').replace(/attachHandlers\(\);\s*loadState\(\);\s*$/,''),context);
  return expression=>vm.runInContext(expression,context);
}
test('removed items do not shift saved pathway identities; all measures have unique IDs',()=>{
  const run=app();
  assert.equal(run("itemById('kisimpfad')"),undefined);
  assert.equal(run("PHASES[0].roles[0].items[2].pathId"),'t2:p-uro:3');
  assert.equal(run('new Set(allItemIds()).size === allItemIds().length'),true);
  assert.equal(run("JSON.stringify(PHASES).includes('Instruktion Fragmin')"),false);
  assert.equal(run("PHASES.find(p=>p.id==='postop-stat').roles[0].items[0].divider"),'OP-Tag');
});
test('interactive questionnaires sum complete answers, including zero and half points',()=>{
  const run=app();
  assert.equal(run("questionnaireScore(QUESTIONNAIRES['fb-g8'],{})"),null);
  run("G8_QUESTIONS.forEach(q=>STATE.answers[q.key]=q.options[q.options.length-1].value)");
  assert.equal(run("questionnaireScore(QUESTIONNAIRES['fb-g8'],STATE.answers)"),17);
  run("STATE.answers.g8_health='0.5'");
  assert.equal(run("questionnaireScore(QUESTIONNAIRES['fb-g8'],STATE.answers)"),15.5);
  run("STOPBANG_QUESTIONS.forEach(q=>STATE.answers[q.key]='0')");
  assert.equal(run("questionnaireScore(QUESTIONNAIRES['fb-stopbang'],STATE.answers)"),0);
  run("EPWORTH_QUESTIONS.forEach(q=>STATE.answers[q.key]='3')");
  assert.equal(run("questionnaireScore(QUESTIONNAIRES['fb-epworth'],STATE.answers)"),24);
  run("STATE.answers.epworth_0='4'");
  assert.equal(run("questionnaireScore(QUESTIONNAIRES['fb-epworth'],STATE.answers)"),null);
});
test('legacy totals remain available without inventing individual answers',()=>{
  const run=app();
  run("STATE.answers.score_g8='12'; STATE.answers.score_ecog='2 = gehfähig'; STATE.checked['t1:fb-g8']=true; migrateQuestionnaireState()");
  assert.equal(run('STATE.legacyScores.score_g8'),'12');
  assert.equal(run('STATE.answers.score_g8'),'');
  assert.equal(run("STATE.checked['t1:fb-g8']"),undefined);
  assert.equal(run('STATE.answers.score_ecog'),'2');
});
test('confirmed source thresholds, optional history and zero scores',()=>{
  const run=app();
  assert.equal(run("FLAG_RULES.kardio({score_mmrc:'0',kardio_ef:''})"),null);
  assert.ok(run("FLAG_RULES.kardio({score_mmrc:'3'})"));
  assert.equal(run("FLAG_RULES.pneumo({score_stopbang:'2',score_epworth:'10'})"),null);
  assert.ok(run("FLAG_RULES.pneumo({score_stopbang:'3'})"));
  assert.ok(run("FLAG_RULES.ernaehrung({score_nrs:'3'})"));
  assert.equal(run("fieldRequired('sucht_alkohol',{})"),false);
  assert.equal(run("fieldRequired('raucher_py',{raucher_status:'Nieraucher'})"),false);
  assert.equal(run("fieldsHTML([{key:'zero',label:'Zero',type:'number'}])").includes('value=""'),true);
  run('STATE.answers.zero=0');
  assert.ok(run("fieldsHTML([{key:'zero',label:'Zero',type:'number'}])").includes('value="0"'));
});
test('case isolation, migration and generated physiotherapy referral',()=>{
  const run=app();
  assert.equal(run('caseStorageKey()'),'bene-eras-case:A');
  run("location.search='?case=B'");
  assert.equal(run('caseStorageKey()'),'bene-eras-case:B');
  run("STATE.checked={'t2:s-pflege:0':true,'t2:p-stoma:0':true}; migrateState()");
  assert.equal(run('Object.keys(STATE.checked).length'),0);
  run("STATE.patientName='QA';STATE.opDate='2026-10-30';STATE.answers={physio_neoblase:'Ja',physio_rehakur:'Nein'}");
  const text=run("referralText('physio')");
  assert.match(text,/QA/);assert.match(text,/2026-10-30/);assert.match(text,/Beckenboden/);assert.match(text,/postoperativ/);
});
