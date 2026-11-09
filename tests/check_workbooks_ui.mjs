import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const script=fs.readFileSync(new URL('../static/workbooks.js',import.meta.url),'utf8'),html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.textContent='';}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}set innerHTML(x){throw Error('Unsafe HTML');}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>[m[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};
let pid=1,writer=true,held=null,heldMatch='',prepared=0;const calls=[];
const structure={sheets:[{name:'Datos',rows:46,max_row:46,formula_count:0,columns:[{column:'A',label:'Sección'},{column:'B',label:'Lista nominal'}]}]};
const packet={metadata:{row_count:45},preview_sha256:'f'.repeat(64),preview:[{location:'Datos!A2,B2',cells:[{label:'Literal <script>',cell:'A2',value:'158'},{label:'Cuenta',cell:'B2',value:null}]}]};
async function api(path,opt={}){calls.push({path,opt});if(held&&path.includes(heldMatch)){const p=held;held=null;return p;}
 if(path.endsWith('/workbooks'))return{items:[{id:9,filename:'Fixture <script>.xlsx'}],can_extract:writer};
 if(path.endsWith('/preview'))return packet;if(path.endsWith('/extract'))return{rows:45,deduplicated:false};return structure;}
const window={};vm.runInNewContext(script,{window,document:{createElement:t=>new Element(t)},JSON,Number,String,Set,Error});
const module=window.NexoWorkbooks.install({api,byId,getProject:()=>pid,onPrepared:async()=>prepared++});const cases=[],check=(name,fn)=>{fn();cases.push(name);};
const text=n=>[n.textContent,...n.children.map(text)].join(' ');
module.resetProject();await module.reload();
check('workbook_list_and_sheet_are_project_scoped',()=>{assert(calls[0].path.includes('/projects/1/'));assert.equal(nodes.workbookSheet.value,'Datos');});
check('sparse_sheet_uses_max_row_not_populated_count',()=>assert.equal(nodes.workbookLast.value,'46'));
nodes.workbookYear.value='2024';await nodes.workbookRead.onclick();
check('preview_has_literal_cell_addresses_and_no_html',()=>{assert(text(nodes.workbookPreview).includes('Literal <script>'));assert(text(nodes.workbookPreview).includes('A2'));});
check('unknown_cell_is_not_zero',()=>assert(text(nodes.workbookPreview).includes('Sin dato')));
check('preview_enables_extract_for_writer',()=>assert.equal(nodes.workbookExtract.disabled,false));
await nodes.workbookExtract.onclick();check('extract_sends_reviewed_selection_and_hash',()=>{const body=JSON.parse(calls.find(c=>c.path.endsWith('/extract')).opt.body);assert.equal(body.preview_sha256,'f'.repeat(64));assert.equal(body.source_year,2024);assert.equal(prepared,1);});
await nodes.workbookRead.onclick();nodes.workbookColumns.value='B';nodes.workbookColumns.oninput();
check('changed_selection_invalidates_previous_preview',()=>assert(nodes.workbookExtract.disabled));
await nodes.workbookRead.onclick();nodes.workbookColumns.value='!';await nodes.workbookExtract.onclick();
check('malformed_changed_selection_is_handled_without_submit',()=>{assert(nodes.workbookExtract.disabled);assert(nodes.workbookStatus.textContent.includes('columnas'));});
await module.reload();writer=false;await module.reload();await nodes.workbookRead.onclick();const count=calls.filter(c=>c.path.endsWith('/extract')).length;await nodes.workbookExtract.onclick();
check('reader_can_preview_but_has_no_extract_control',()=>{assert(nodes.workbookExtract.hidden);assert.equal(calls.filter(c=>c.path.endsWith('/extract')).length,count);});
writer=true;let resolve;held=new Promise(r=>resolve=r);heldMatch='/workbooks';const old=module.reload();pid=2;module.resetProject();resolve({items:[{id:99,filename:'OLD'}],can_extract:true});await old;
check('late_list_is_discarded_after_project_change',()=>assert.equal(nodes.workbookFile.children.length,0));
pid=1;await module.reload();let resolve2;held=new Promise(r=>resolve2=r);heldMatch='/preview';const preview=nodes.workbookRead.onclick();module.resetProject();resolve2(packet);await preview;
check('same_project_reset_invalidates_pending_preview',()=>{assert.equal(nodes.workbookPreview.children.length,0);assert(nodes.workbookExtract.disabled);});
await module.reload();await nodes.workbookRead.onclick();let resolve3;held=new Promise(r=>resolve3=r);heldMatch='/extract';const saving=nodes.workbookExtract.onclick();
check('pending_extraction_blocks_project_switch',()=>assert.equal(module.canLeaveProject(),false));resolve3({rows:45});await saving;
check('completed_extraction_releases_project_switch',()=>assert(module.canLeaveProject()));
pid=null;module.resetProject();const before=calls.length;await module.reload();check('no_project_does_not_query',()=>assert.equal(calls.length,before));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
