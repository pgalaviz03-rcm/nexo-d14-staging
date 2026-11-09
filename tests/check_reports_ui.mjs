import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const script=fs.readFileSync(new URL('../static/reports.js',import.meta.url),'utf8');
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.listeners={};this.style={};}
 set innerHTML(value){throw Error('Untrusted HTML must not be rendered');}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 addEventListener(name,fn){this.listeners[name]=fn;}
 click(){this.clicked=true;}
}
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
const byId=id=>{assert(nodes[id],id);return nodes[id];};
nodes.reportForm.reset=()=>{for(const id of ['reportTitle','reportQuestion','reportNote'])nodes[id].value='';nodes.reportKind.value='all';};
const window={};const routes=[];let current=0,published=null,allowWrite=true;
const versions=[];
const snapshot=note=>({title:'Informe <img src=x onerror=alert(1)>',editorial_note:note,
 context:{question:'agua',coverage:{bounded:false,not_indexed:[]},citations:[{citation:'N1',title:'Archivo <script>',source:'Fixture',excerpt:'Literal <b>texto</b>',url:'https://example.org/a'}]},
 scope:'Extractos y nota',filters:{source_kind:'all'}});
async function api(path,options={}){
 routes.push({path,options});const method=options.method||'GET';
 const body=options.body?JSON.parse(options.body):{};
 if(path.endsWith('/reports')&&method==='GET')return{items:current?[{id:1,title:'Informe',version:allowWrite?current:published,published_version:published,citations:1}]:[],published_count:published?1:0,can_write:allowWrite,can_publish:allowWrite};
 if(method==='POST'&&path.endsWith('/release')){assert.equal(body.expected_version,current);published=current;return{id:1,published_version:published};}
 if(method==='POST'){
  assert(!('citations' in body));if(current)assert.equal(body.expected_version,current);
  current++;versions.push(snapshot(body.note));return{id:1,version:current};
 }
 if(path.endsWith('/versions'))return versions.map((x,i)=>({version:i+1,created_at:'2026-10-19T12:00:00Z'})).reverse();
 const match=path.match(/\/versions\/(\d+)/);const v=match?Number(match[1]):allowWrite?current:published;
 return{id:1,version:v,current_version:allowWrite?current:v,published_version:published,created_at:'2026-10-19T12:00:00Z',sha256:'fixture',snapshot:versions[v-1]};
}
vm.runInNewContext(script,{window,document:{createElement:tag=>new Element(tag)},confirm:()=>true,
 setTimeout:fn=>fn(),Blob,URL:{createObjectURL:()=> 'blob:synthetic-test',revokeObjectURL(){}},console});
let page;
const module=window.NexoReports.install({api,byId,page:name=>page=name,getProject:()=>1});
await module.reload();assert.equal(nodes.summaryReports.textContent,0);
module.prepare('agua','documents',3);
assert.equal(nodes.reportDocumentScope.hidden,false);assert.equal(nodes.reportKind.disabled,true);assert.equal(nodes.reportClearScope.hidden,false);
module.prepare('agua');assert.equal(page,'reports');
assert.equal(nodes.reportDocumentScope.hidden,false);assert(nodes.reportDocumentScope.textContent.includes('noticias y documentos del proyecto'));assert.equal(nodes.reportKind.disabled,false);
nodes.reportTitle.value='Informe';nodes.reportNote.value='Primera nota';
await nodes.reportForm.listeners.submit({preventDefault(){}});
assert.equal(current,1);assert.equal(nodes.reportPublish.hidden,false);
await nodes.reportPublish.onclick();assert.equal(published,1);
nodes.reportNote.value='Segunda nota';nodes.reportForm.listeners.input();
await nodes.reportForm.listeners.submit({preventDefault(){}});
assert.equal(current,2);assert.equal(published,1);
await nodes.reportVersions.onclick();
await nodes.reportVersionList.children.find(x=>x.textContent.startsWith('Versión 1')).onclick();
assert.equal(nodes.reportSave.disabled,true);assert.equal(nodes.reportNote.value,'Primera nota');
await nodes.reportExport.onclick();assert(routes.at(-1).path.endsWith('/versions/1/export'));
allowWrite=false;await module.reload();
assert.equal(nodes.reportForm.hidden,true);assert.equal(nodes.reportNew.hidden,true);
assert.equal(nodes.uploadDataset.hidden,true);
allowWrite=true;versions[current-1].mode='explorer_selection_v1';await module.reload();await module.open(1);assert.equal(nodes.reportForm.hidden,true);
console.log(JSON.stringify({controller_cases:['create','release','append_version','historical_readonly','export','reader_controls','literal_source_rendering','frozen_explorer_selection','document_scope_visible_on_open'],passed:true,browser_rendering:false}));

