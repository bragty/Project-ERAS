const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
// The structure of definition.json is checked by the Python system check
// (apps/checklist/definition_checks.py); custom blocks are rendered only here.
test('every custom block used in definition.json is rendered by the frontend',()=>{
  const definition=fs.readFileSync(path.join(__dirname,'../apps/checklist/definition.json'),'utf8');
  const ctx=vm.createContext({document:{addEventListener(){},getElementById:()=>({textContent:definition})},URLSearchParams,Date});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'static/eras/js/checklist.js'),'utf8'),ctx);
  const parsed=JSON.parse(definition);
  const items=parsed.preop.concat(...parsed.phases.flatMap(p=>p.roles.map(r=>r.items))).filter(it=>!it.divider);
  for(const item of items){
    if(item.custom) assert.notEqual(vm.runInContext(`customHTML(${JSON.stringify(item.custom)})`,ctx),'',`${item.id}: custom '${item.custom}' wird in customHTML nicht dargestellt`);
  }
});
