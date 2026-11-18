const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function app(){
  const definition=fs.readFileSync(path.join(__dirname,'../apps/checklist/definition.json'),'utf8');
  const ctx=vm.createContext({document:{addEventListener(){},getElementById:()=>({textContent:definition})},URLSearchParams,Date});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'static/eras/js/checklist.js'),'utf8'),ctx);
  const run=code=>vm.runInContext(code,ctx);
  run(`let alerts=[];let saves=0;let confirmations=0;
       alert=m=>alerts.push(m);confirm=()=>{confirmations++;return true;};
       renderChecklist1=()=>{};updateProgress=()=>{};renderDerived=()=>{};scheduleSave=()=>saves++;
       document.querySelector=()=>({checked:true});
       document.querySelectorAll=()=>[{dataset:{labImportIndex:'0'}}];
       STATE.labs=[];
       LAB_IMPORT_PREVIEW={patientMatch:{status:'unverified'},suggestions:[{
         labId:'hb',labLabel:'Hämoglobin',originalLabel:'Hämoglobin',normalizedValue:'124',normalizedUnit:'g/l',
         originalValue:'124',originalUnit:'g/l',status:'review',
         extractionMethod:'ocr',sourceHash:'test',templateId:'kisim-single-result-v1'
       }]};`);
  return run;
}
test('OCR proposals require selection and cannot be reassigned to another parameter',()=>{
  const run=app(); const html=run('labImportPreviewHTML()');
  assert.match(html,/data-lab-patient-confirm/);
  assert.doesNotMatch(html,/data-lab-import-index="0" checked/);
  assert.match(html,/<select disabled aria-label="Erkannter Laborparameter"/);
  assert.doesNotMatch(html,/Anderer Wert/);
});
test('confirming imports fills the existing fields exactly and cannot be repeated',()=>{
  const run=app();run('applyLabImport();applyLabImport()');
  assert.deepEqual(JSON.parse(run('JSON.stringify(STATE.labs.map(r=>[r.type,r.value,r.unit]))')),[['Hämoglobin','124','g/l']]);
  assert.equal(run('saves'),1);
});
test('unknown parameters, id mismatch and invalid numeric values are rejected',()=>{
  for(const mutation of ["labLabel='MCV'","labLabel='Anderer Wert'","labId='crp'","normalizedValue='1 2'","normalizedUnit='' "]){
    const run=app();run('LAB_IMPORT_PREVIEW.suggestions[0].'+mutation);run('applyLabImport()');
    assert.equal(run('STATE.labs.length'),0); assert.equal(run('alerts.length'),1);
  }
});
test('existing values require an additional explicit replacement confirmation',()=>{
  const run=app();run("STATE.labs=[{type:'Hämoglobin',value:'100',unit:'g/l'}];confirm=()=>{confirmations++;return false;};applyLabImport()");
  assert.equal(run('confirmations'),1);assert.equal(run('STATE.labs[0].value'),'100');assert.equal(run('saves'),0);
});
test('a lab parameter cannot be selected twice in manual rows',()=>{
  const run=app();run("STATE.labs=[{type:'Hämoglobin',value:'124',unit:'g/l'},{type:'',value:'',unit:''}]");
  assert.match(run('labOptionsHTML(1,"")'),/value="Hämoglobin"  disabled>Hämoglobin \(bereits erfasst\)/);
  assert.doesNotMatch(run('labOptionsHTML(1,"")'),/value="Anderer Wert"[^>]*disabled/);
  assert.equal(run("setLabField({dataset:{labIdx:'1',labKey:'type'},value:'Hämoglobin'})"),false);
  assert.equal(run('STATE.labs[1].type'),'');assert.equal(run('alerts.length'),1);
  assert.equal(run("setLabField({dataset:{labIdx:'1',labKey:'type'},value:'CRP'})"),true);
  assert.equal(run('STATE.labs[1].type'),'CRP');
});
test('legacy labels stay visible in stored rows but are not selectable',()=>{
  const run=app();run("STATE.labs=[{type:'BNP',value:'90',unit:'ng/l'}]");
  const html=run('labOptionsHTML(0,"BNP")');
  assert.match(html,/value="BNP" selected>BNP \(nicht mehr auswählbar\)/);
  assert.doesNotMatch(run('labOptionsHTML(0,"")'),/value="BNP"/);
});
test('without recognized values only a close button is offered',()=>{
  const run=app();run('LAB_IMPORT_PREVIEW.suggestions=[]');
  const html=run('labImportPreviewHTML()');
  assert.match(html,/Es wurden keine unterstützten Werte erkannt/);
  assert.doesNotMatch(html,/data-lab-patient-confirm|lab-import-patient/);
  assert.doesNotMatch(html,/data-lab-import-apply/);
  assert.match(html,/data-lab-import-cancel>Schliessen</);
});
test('identical recorded values are only listed in the summary, not offered again',()=>{
  const run=app();run("STATE.labs=[{type:'Hämoglobin',value:'124',unit:'g/l',importMeta:{sourceHash:'test',labId:'hb'}}]");
  const html=run('labImportPreviewHTML()');
  assert.doesNotMatch(html,/data-lab-import-index="0"/);
  assert.match(html,/1 Wert ist bereits identisch erfasst/);
  assert.match(html,/Alle erkannten Werte sind bereits identisch erfasst/);
  assert.doesNotMatch(html,/data-lab-import-apply/);
  assert.match(html,/data-lab-import-cancel>Schliessen</);
  run('applyLabImport()');
  assert.equal(run('saves'),0);assert.equal(run('alerts.length'),1);
});
test('values compare by content: "124,0 g/L" equals 124 g/l, a changed value stays selectable',()=>{
  const run=app();run("STATE.labs=[{type:'Hämoglobin',value:'124,0',unit:'g/L'}]");
  assert.match(run('labImportPreviewHTML()'),/bereits identisch erfasst/);
  run("STATE.labs=[{type:'Hämoglobin',value:'130',unit:'g/l',importMeta:{sourceHash:'test',labId:'hb'}}]");
  const html=run('labImportPreviewHTML()');
  assert.match(html,/data-lab-import-index="0"(?![^>]*disabled)/);
  assert.match(html,/Bereits erfasst: 130 g\/l/);
  assert.match(html,/data-lab-import-apply/);
  run('applyLabImport()');
  assert.equal(run('STATE.labs[0].value'),'124');assert.equal(run('confirmations'),1);
});
test('HbA1c preview shows the server measure only for the value it was computed for',()=>{
  const run=app();
  run(`LAB_IMPORT_PREVIEW.suggestions=[{labId:'hba1c',labLabel:'HbA1c',originalLabel:'HbAlc',normalizedValue:'8.9',normalizedUnit:'%',
    comparisonOperator:'',status:'review',sourceHash:'x',templateId:'kisim-single-result-v1',
    assessment:{status:'action',value:'8.9 %',group:'Nicht-Diabetiker/in',message:'HbA1c > 6.4 %: Kontakt Hausarzt',note:'',assessedFor:'8.9|%'}}]`);
  let html=run('labImportPreviewHTML()');
  assert.match(html,/HbA1c 8.9 % – Nicht-Diabetiker\/in/);
  assert.match(html,/clinical-warning/);
  run("LAB_IMPORT_PREVIEW.suggestions[0].normalizedValue='5.2'");
  html=run('labImportPreviewHTML()');
  assert.doesNotMatch(html,/Kontakt Hausarzt/);
  assert.match(html,/HbA1c-Beurteilung erscheint nach der Übernahme/);
});
test('confirmed replacement overwrites the existing value and stores no measurement time',()=>{
  const run=app();run("STATE.labs=[{type:'Hämoglobin',value:'100',unit:'g/l'}];applyLabImport()");
  assert.equal(run('confirmations'),1);
  assert.deepEqual(JSON.parse(run('JSON.stringify(STATE.labs.map(r=>[r.type,r.value,r.unit]))')),[['Hämoglobin','124','g/l']]);
  assert.equal(run("'measurementAt' in STATE.labs[0].importMeta"),false);
});
