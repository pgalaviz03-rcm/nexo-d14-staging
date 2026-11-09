/* Exercise the reused territory controller; no browser or external network. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8'),inline=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const code=inline.slice(inline.indexOf('// Real local data extracted'),inline.indexOf('// v0.3:'));
class Element{
 constructor(){this.value='';this.checked=false;this.hidden=false;this.listeners={};this.classes=new Set();this.dataset={};this.innerHTML='';this.disabled=false;
  this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),toggle:(x,on)=>on?this.classes.add(x):this.classes.delete(x)};}
 addEventListener(k,f){this.listeners[k]=f;}replaceChildren(){this.innerHTML='';}scrollIntoView(){}
}
const ids=['territoryEmpty','territoryContent','exportHist','sectionSearch','toggleManzana','map-manzanas','sectionCount','sectionRows','selectedSection'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()])),paths=[...html.matchAll(/class="secpath" data-section="(\d+)"/g)].map(x=>{const n=new Element();n.dataset.section=x[1];return n;});
const byId=id=>{assert(nodes[id],id);return nodes[id];};let downloads=0,requested=[],fetchImpl=async()=>({ok:true,blob:async()=>({})});
const context={byId,projectHistoryReady:false,activeProjectId:1,authToken:'synthetic-test-only',
 document:{querySelectorAll:q=>q==='.secpath'?paths:[],querySelector:()=>null,createElement:()=>({click(){downloads++;}})},
 fetch:(path,options)=>{requested.push({path,options});return fetchImpl();},URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL(){}},
 setTimeout:f=>f(),modal(){throw Error('Unexpected modal');}};
vm.createContext(context);vm.runInContext(code+';this.load=loadTerritory;this.clear=resetTerritory;this.selected=()=>activeSection;',context);
const rows=Object.values(JSON.parse(fs.readFileSync(new URL('../data/secciones_2024.json',import.meta.url),'utf8'))).map(x=>({...x,year:2024}));
const tests=[],check=(name,fn)=>{fn();tests.push(name);};
context.load({slug:'d14'},{official_votes:41992},rows);
check('reused_45_section_map',()=>{assert.equal(paths.length,45);assert.equal(context.projectHistoryReady,true);assert.equal(nodes.territoryContent.hidden,false);assert.equal(nodes.sectionCount.textContent,'45 secciones');});
check('initial_section_detail',()=>{assert.equal(context.selected(),'521');assert(nodes.selectedSection.innerHTML.includes('Sección 521'));});
nodes.sectionSearch.value='146';nodes.sectionSearch.listeners.input();
check('search_section',()=>{assert.equal(nodes.sectionCount.textContent,'1 secciones');assert(nodes.sectionRows.innerHTML.includes('data-id="146"'));});
paths.find(p=>p.dataset.section==='146').listeners.click();check('map_selects_table_detail',()=>assert.equal(context.selected(),'146'));
paths.find(p=>p.dataset.section==='147').listeners.keydown({key:'Enter',preventDefault(){}});check('keyboard_selection',()=>assert.equal(context.selected(),'147'));
nodes.toggleManzana.checked=true;nodes.toggleManzana.listeners.change({target:nodes.toggleManzana});check('block_layer',()=>assert(nodes['map-manzanas'].classes.has('on')));
context.activeProjectId=2;context.load({slug:'other'},{official_votes:41992},rows);
check('other_project_never_shows_d14',()=>{assert.equal(nodes.territoryContent.hidden,true);assert.equal(nodes.territoryEmpty.hidden,false);assert.equal(nodes.sectionRows.innerHTML,'');assert.equal(nodes.exportHist.disabled,true);});
check('project_reset_clears_search_selection_layer',()=>{assert.equal(nodes.sectionSearch.value,'');assert.equal(context.selected(),null);assert.equal(nodes.toggleManzana.checked,false);assert(!nodes['map-manzanas'].classes.has('on'));assert(paths.every(p=>!p.classes.has('is-active')));});
await nodes.exportHist.onclick();check('no_export_when_no_valid_territory',()=>assert.equal(requested.length,0));
context.activeProjectId=1;context.load({slug:'d14'},{},rows);check('missing_validation_does_not_display_map',()=>assert.equal(context.projectHistoryReady,false));
context.load({slug:'d14'},{official_votes:41992},rows.slice(0,44));check('partial_history_is_not_complete_map',()=>assert.equal(context.projectHistoryReady,false));
context.load({slug:'d14'},{official_votes:41992},rows);await nodes.exportHist.onclick();
check('authorized_own_project_export',()=>{assert.equal(downloads,1);assert.equal(requested.at(-1).path,'/api/projects/1/sections/export');assert.equal(requested.at(-1).options.headers.Authorization,'Bearer synthetic-test-only');});
let complete;fetchImpl=()=>new Promise(r=>complete=r);const pending=nodes.exportHist.onclick();context.clear();context.load({slug:'d14'},{official_votes:41992},rows);
complete({ok:true,blob:async()=>({})});await pending;check('late_export_discarded_after_reset_even_same_project',()=>assert.equal(downloads,1));
let finishBlob;fetchImpl=async()=>({ok:true,blob:()=>new Promise(r=>finishBlob=r)});const reading=nodes.exportHist.onclick();await new Promise(setImmediate);context.activeProjectId=2;context.clear();finishBlob({});await reading;
check('late_blob_discarded_after_project_change',()=>{assert.equal(downloads,1);assert.equal(nodes.exportHist.disabled,true);});
console.log(JSON.stringify({passed:true,cases:tests,browser_visual_acceptance:false}));
