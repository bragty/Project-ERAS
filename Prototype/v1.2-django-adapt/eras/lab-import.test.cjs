const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function app(){
  const ctx=vm.createContext({document:{},URLSearchParams,Date});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'static/eras/js/checklist.js'),'utf8'),ctx);
  const run=code=>vm.runInContext(code,ctx);
  run(`let alerts=[];let saves=0;let confirmations=0;
       alert=m=>alerts.push(m);confirm=()=>{confirmations++;return true;};
       renderChecklist1=()=>{};updateProgress=()=>{};updateFlags=()=>{};scheduleSave=()=>saves++;
       document.querySelector=()=>({checked:true});
       document.querySelectorAll=()=>[{dataset:{labImportIndex:'0'}}];
       STATE.labs=[];
       LAB_IMPORT_PREVIEW={patientMatch:{status:'unverified'},suggestions:[{
         labId:'hb',labLabel:'Hb',originalLabel:'Hämoglobin',normalizedValue:'124',normalizedUnit:'g/l',
         originalValue:'124',originalUnit:'g/l',status:'review',measurementAt:'2026-08-01T11:30',
         extractionMethod:'ocr',sourceHash:'test',templateId:'kisim-single-result-v1'
       }]};`);
  return run;
}
test('OCR proposals require selection and cannot be reassigned to another parameter',()=>{
  const run=app(); const html=run('labImportPreviewHTML()');
  assert.doesNotMatch(html,/data-lab-import-index="0" checked/);
  assert.match(html,/<select disabled aria-label="Erkannter Laborparameter"/);
  assert.doesNotMatch(html,/Anderer Wert/);
});
test('confirming imports fills the existing fields exactly and cannot be repeated',()=>{
  const run=app();run('applyLabImport();applyLabImport()');
  assert.deepEqual(JSON.parse(run('JSON.stringify(STATE.labs.map(r=>[r.type,r.value,r.unit]))')),[['Hb','124','g/l']]);
  assert.equal(run('saves'),1);
});
test('unknown parameters, id mismatch and invalid numeric values are rejected',()=>{
  for(const mutation of ["labLabel='eGFR'","labLabel='Anderer Wert'","labId='crp'","normalizedValue='1 2'","normalizedUnit='' "]){
    const run=app();run('LAB_IMPORT_PREVIEW.suggestions[0].'+mutation);run('applyLabImport()');
    assert.equal(run('STATE.labs.length'),0); assert.equal(run('alerts.length'),1);
  }
});
test('existing values require an additional explicit replacement confirmation',()=>{
  const run=app();run("STATE.labs=[{type:'Hb',value:'100',unit:'g/l'}];confirm=()=>{confirmations++;return false;};applyLabImport()");
  assert.equal(run('confirmations'),1);assert.equal(run('STATE.labs[0].value'),'100');assert.equal(run('saves'),0);
});
