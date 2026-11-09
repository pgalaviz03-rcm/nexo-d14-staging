import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.listeners={};this.style={};}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}addEventListener(name,fn){this.listeners[name]=fn;}set innerHTML(v){throw Error('Unsafe HTML');}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(r=>[r[1],new Element()]));
const byId=id=>{assert(nodes[id],id);return nodes[id];};nodes.reportForm.reset=()=>{for(const id of ['reportTitle','reportQuestion','reportNote'])nodes[id].value='';nodes.reportKind.value='all';};
let saved=null,body=null;const cases=[],check=(name,fn)=>{fn();cases.push(name);};
async function api(path,options={}){
 if(options.method==='POST'){body=JSON.parse(options.body);saved={id:1,version:1,current_version:1,published_version:null,created_at:'2026-10-21T00:00:00Z',sha256:'test',snapshot:{title:body.title,editorial_note:body.note,filters:{source_kind:body.source_kind,document_id:body.document_id},context:{question:body.question,coverage:{bounded:false},citations:[{title:'PDF',source:'PDF · página 1',excerpt:'Agua',page:1,dataset_id:body.document_id}]}}};return{id:1,version:1};}
 if(path.endsWith('/reports'))return{can_write:true,can_publish:false,published_count:0,items:[]};
 return saved;
}
const context={window:{},document:{createElement:t=>new Element(t)},api,byId,confirm:()=>true,Blob,URL,setTimeout,console};vm.createContext(context);
vm.runInContext(fs.readFileSync(new URL('../static/reports.js',import.meta.url),'utf8'),context);
context.reportsModule=context.window.NexoReports.install({api,byId,page:()=>{},getProject:()=>1});await context.reportsModule.reload();
const binding=html.split('\n').find(line=>line.startsWith("byId('knowledgePrepareReport').onclick="));assert(binding);vm.runInContext(binding,context);
nodes.knowledgeQuery.value='Changed after search';nodes.knowledgeKind.value='all';
context.libraryModule={selectedId:()=>999};context.lastContextPacket={question:'rezago',source_kind:'documents',document_id:3,citations:[{page:1,dataset_id:3}]};
nodes.knowledgePrepareReport.onclick();
check('handoff_uses_successful_query_not_mutated_form',()=>assert.equal(nodes.reportQuestion.value,'rezago'));
check('handoff_displays_scoped_source_immediately',()=>{assert.equal(nodes.reportKind.value,'documents');assert.equal(nodes.reportKind.disabled,true);});
await context.reportsModule.reload();nodes.reportTitle.value='Informe del PDF';nodes.reportNote.value='Revisión';nodes.reportForm.listeners.input();
await nodes.reportForm.listeners.submit({preventDefault(){}});
check('handoff_sends_selected_document_to_server',()=>assert.equal(body.document_id,3));
check('handoff_never_sends_broadened_source_kind',()=>assert.equal(body.source_kind,'documents'));
check('reopened_report_keeps_document_scope',()=>assert.equal(nodes.reportKind.disabled,true));
context.lastContextPacket={question:'agua',source_kind:'news',document_id:null,citations:[{kind:'news'}]};nodes.knowledgePrepareReport.onclick();
check('global_news_scope_is_not_changed_to_all_sources',()=>{assert.equal(nodes.reportKind.value,'news');assert(nodes.reportDocumentScope.textContent.includes('noticias del proyecto'));});
context.lastContextPacket=null;nodes.reportQuestion.value='unchanged';nodes.knowledgePrepareReport.onclick();
check('missing_search_packet_cannot_prepare_a_report',()=>assert.equal(nodes.reportQuestion.value,'unchanged'));
context.lastContextPacket={question:'nothing',citations:[]};nodes.knowledgePrepareReport.onclick();
check('empty_search_packet_cannot_prepare_a_report',()=>assert.equal(nodes.reportQuestion.value,'unchanged'));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
