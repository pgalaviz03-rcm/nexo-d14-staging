import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8'),script=fs.readFileSync(new URL('briefing.js',base),'utf8');
const fixture=JSON.parse(fs.readFileSync(new URL('fixtures/briefing-ui.json',import.meta.url),'utf8'));
class Element{
 constructor(){this.children=[];this.value='';this.style={};this.hidden=false;this.disabled=false;this.listeners={};}
 set innerHTML(value){throw Error('Untrusted HTML rendering');}
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}
 addEventListener(k,fn){this.listeners[k]=fn;}click(){this.clicked=true;}
}
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]),nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
const byId=id=>{assert(nodes[id],id);return nodes[id];};byId('briefingPeriod').value='7';
byId('briefingSaveForm').reset=()=>{byId('briefingTitle').value='';byId('briefingNote').value='';};
let project=1,saveFailure=false,readonly=false,received,saved,exported,defer=null;
async function api(path,options={}){
 assert(path.startsWith('/api/projects/'+project+'/briefing'));
 if(options.method==='POST'){received=JSON.parse(options.body);if(saveFailure)throw Error('La evidencia cambió; actualiza el corte.');return {id:7,version:1,published:false};}
 if(defer)return new Promise(r=>{defer.resolve=r;});
 return {...structuredClone(fixture),can_save:!readonly};
}
const window={};vm.runInNewContext(script,{window,document:{createElement:()=>new Element()},Date,URLSearchParams,Blob,
 URL:{createObjectURL:blob=>{exported=blob;return 'blob:fixture';},revokeObjectURL(){}},setTimeout:fn=>fn(),confirm:()=>false});
const module=window.NexoBriefing.install({api,byId,getProject:()=>project,onSaved:async id=>saved=id});
await module.reload();assert.equal(nodes.briefingNewsCount.textContent,'1');assert.equal(nodes.briefingAlerts.textContent,'—');
assert.equal(nodes.briefingNews.children[0].children[1].textContent,'Fuente <script>literal</script>');
nodes.briefingNote.value='Nota editorial';nodes.briefingSaveForm.listeners.input();assert.equal(module.canLeaveProject(),false);
await nodes.briefingSaveForm.onsubmit({preventDefault(){}});assert.equal(saved,7);assert.equal(received.note,'Nota editorial');assert(!('citations' in received));assert.equal(received.preview_sha256,fixture.preview_sha256);assert.equal(module.canLeaveProject(),true);
nodes.briefingExport.onclick();assert.equal(JSON.parse(await exported.text()).editorial_note,'Nota editorial');
saveFailure=true;nodes.briefingNote.value='No perder esta nota';nodes.briefingSaveForm.listeners.input();await nodes.briefingSaveForm.onsubmit({preventDefault(){}});assert.equal(nodes.briefingNote.value,'No perder esta nota');assert(nodes.briefingStatus.textContent.includes('cambió'));
readonly=true;await module.reload();assert.equal(nodes.briefingSavePanel.hidden,true);assert.equal(nodes.briefingExport.disabled,false);
defer={};const pending=module.reload();project=2;module.resetProject();defer.resolve({...fixture,can_save:true});await pending;assert.equal(nodes.briefingNews.children.length,0);assert.equal(nodes.briefingTitle.value,'');
defer=null;readonly=false;await module.reload();nodes.briefingPeriod.value='custom';nodes.briefingPeriod.onchange();assert.equal(nodes.briefingExport.disabled,true);assert.equal(nodes.briefingSave.disabled,true);
nodes.reportForm.reset=()=>{};
vm.runInNewContext(fs.readFileSync(new URL('reports.js',base),'utf8'),{window,document:{createElement:()=>new Element()},Date,Blob,URL,confirm:()=>true,setTimeout:fn=>fn()});
const reportApi=async path=>path.endsWith('/reports')?{items:[{id:7,title:'Briefing',version:1,citations:1,published_version:null}],published_count:0,can_write:true,can_publish:true}:{id:7,version:1,current_version:1,published_version:null,created_at:fixture.prepared_at,sha256:'fixture',snapshot:{mode:fixture.mode,title:'Briefing guardado',editorial_note:'Nota del autor',context:{question:'Briefing',citations:fixture.citations,coverage:fixture.coverage},filters:{source_kind:'all'},scope:fixture.interpretation,briefing:fixture}};
const reports=window.NexoReports.install({api:reportApi,byId,getProject:()=>1,page:()=>{}});await reports.reload();await reports.open(7);
assert.equal(nodes.reportForm.hidden,true);assert.equal(nodes.reportPublish.hidden,false);assert.equal(nodes.reportExport.hidden,false);
console.log(JSON.stringify({passed:true,cases:['actual_counts','unknown_alerts','literal_sources','unsaved_note_guard','save_only_filters_and_hash','editorial_note_export','stale_cut_note_preserved','viewer_controls','late_project_response_discarded','changed_dates_invalidate_cut','frozen_briefing_report_controls'],browser_visual_acceptance:false}));
