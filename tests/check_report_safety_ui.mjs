/* Reports permissions, filter semantics and stale request protection; simulated DOM. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.style={};this.listeners={};}set innerHTML(v){throw Error('Unsafe HTML');}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}addEventListener(k,f){this.listeners[k]=f;}click(){if(this.tagName==='a')downloads.push(this.download);}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};nodes.reportForm.reset=()=>{for(const id of ['reportTitle','reportNote','reportQuestion'])nodes[id].value='';nodes.reportKind.value='all';};
const snapshot={title:'Informe ÁGUA <script>literal</script>',editorial_note:'Saved note',context:{question:'agua',coverage:{bounded:false,not_indexed:[]},citations:[{citation:'N1',title:'Title <script>literal</script>',source:'Source',excerpt:'Text <b>literal</b>',url:'https://example.org/source'}]},filters:{source_kind:'all'},scope:'Saved sources'};
const item=(id,origin,state)=>({id,title:id===1?snapshot.title:'Report '+id,origin,state,version:id===1?2:1,published_version:state==='draft'?null:1,citations:1,created_at:'2026-10-20T12:00:00Z'});
let project=1,allow=true,held=null,requests=[],downloads=[],blobs=[],conflict=false,resetOnBlob=false,pages=[];
const details=id=>({id,version:id===1?2:1,current_version:id===1?2:1,published_version:id===3?null:1,is_released:id===2,created_at:'2026-10-20T12:00:00Z',sha256:'fixture',snapshot:{...structuredClone(snapshot),...(id===3?{mode:'explorer_selection_v1'}:id===2?{mode:'local_documentary_briefing_v1',briefing:{filters:{start:'2026-10-19T12:00:00Z',end:'2026-10-20T12:00:00Z'},news_count:3,pulse:{metrics:{mentions:4},active_alerts:null,alerts:[]},content_analytics:{pieces:4,tone_classified:0,mood_index:null,mockery_percentage:null,tone:[],emotions:[{emotion:'fear',percentage:null}]}}}:{})}});
function route(path,options){if(options.method==='POST')return 'write';if(path.endsWith('/reports'))return 'list';if(path.endsWith('/versions'))return 'versions';if(path.endsWith('/export'))return 'export';if(path.endsWith('/document'))return 'document';return 'detail';}
async function api(path,options={}){requests.push({path,options});assert(path.startsWith('/api/projects/'+project+'/reports'));const type=route(path,options);
 if(held?.type===type)return new Promise((resolve,reject)=>{held.resolve=resolve;held.reject=reject;});
 if(type==='list')return {items:[item(1,'documentary','updated'),item(2,'briefing','released'),item(3,'selection','draft')],published_count:2,can_write:allow,can_publish:allow};
 if(type==='versions')return [{version:2,created_at:'2026-10-20T12:00:00Z'},{version:1,created_at:'2026-10-19T12:00:00Z'}];
 if(type==='write'){if(conflict)throw Error('Otra persona guardó cambios');return {id:1,version:2};}
 if(type==='document')return {html:'<!doctype html><p>Literal &lt;script&gt;</p>',report_id:1,version:2};
 const id=Number(path.match(/reports\/(\d+)/)[1]),d=details(id),version=path.match(/versions\/(\d+)/);if(version)d.version=Number(version[1]);return d;
}
const window={};vm.runInNewContext(fs.readFileSync(new URL('reports.js',base),'utf8'),{window,document:{createElement:t=>new Element(t)},Date,Intl,Blob,confirm:()=>false,setTimeout:f=>f(),URL:{createObjectURL:b=>{blobs.push(b);if(resetOnBlob){project=2;module.resetProject();resetOnBlob=false;}return 'blob:fixture';},revokeObjectURL(){}}});
const module=window.NexoReports.install({api,byId,page:p=>pages.push(p),getProject:()=>project});
async function reset(){held=null;project=1;allow=true;module.resetProject();await module.reload();await module.open(1);}
const tests=[],check=(name,f)=>{f();tests.push(name);};await reset();
check('archive_states_are_distinct',()=>{assert.equal(nodes.reportCount.textContent,'3');assert.equal(nodes.reportDraftCount.textContent,'1');assert.equal(nodes.reportReleasedCount.textContent,'1');assert.equal(nodes.reportUpdatedCount.textContent,'1');});
nodes.reportSearch.value='agua';nodes.reportSearch.oninput();check('title_filter_ignores_case_and_accents',()=>assert.equal(nodes.reportList.children.length,1));
nodes.reportSearch.value='';nodes.reportTypeFilter.value='selection';nodes.reportTypeFilter.onchange();check('origin_filter_uses_saved_type',()=>assert.equal(nodes.reportList.children[0].children[1].textContent,'Report 3'));
await module.open(3);check('frozen_selection_hides_search_revision_form',()=>assert(nodes.reportForm.hidden));nodes.reportOrigin.onclick();check('frozen_origin_returns_to_explorer',()=>assert.equal(pages.at(-1),'listening'));
await module.open(2);check('saved_briefing_unknowns_stay_unknown',()=>{const text=nodes.reportBody.children.map(c=>c.textContent||'').join(' ');assert(text.includes('Miedo: — %'));assert(text.includes('— señales activadas'));});
await reset();await module.open(1,1);const before=requests.filter(r=>r.options.method==='POST').length;await nodes.reportPublish.onclick();await nodes.reportForm.listeners.submit({preventDefault(){}});
check('historical_controls_cannot_publish_or_revise_unreviewed_head',()=>assert.equal(requests.filter(r=>r.options.method==='POST').length,before));
await reset();nodes.reportNote.value='Keep unsaved';nodes.reportForm.listeners.input();await module.reload();
check('list_refresh_preserves_unsaved_note',()=>{assert.equal(nodes.reportNote.value,'Keep unsaved');assert.equal(module.canLeaveProject(),false);});
conflict=true;await nodes.reportForm.listeners.submit({preventDefault(){}});conflict=false;
check('stale_save_keeps_note_and_expected_viewed_version',()=>{const b=JSON.parse(requests.filter(r=>r.options.method==='POST').at(-1).options.body);assert.equal(b.expected_version,2);assert.equal(nodes.reportNote.value,'Keep unsaved');assert(nodes.reportMessage.textContent.includes('Otra persona'));assert(!('user_id' in b));});
await reset();await nodes.reportDocument.onclick();check('printable_document_is_downloaded_without_inserting_html',()=>{assert.equal(downloads.at(-1),'NEXO_Informe_1_v2.html');assert(blobs.at(-1).type.startsWith('text/html'));});
await reset();held={type:'export'};const lateExport=nodes.reportExport.onclick(),n=downloads.length;project=2;module.resetProject();held.resolve(details(1));await lateExport;
check('late_export_never_downloads_in_next_project',()=>assert.equal(downloads.length,n));
await reset();held={type:'versions'};const lateVersions=nodes.reportVersions.onclick();project=2;module.resetProject();project=1;module.resetProject();held.resolve([{version:1,created_at:'fixture'}]);await lateVersions;
check('late_versions_discarded_even_returning_to_same_project',()=>assert.equal(nodes.reportVersionList.children.length,0));
await reset();held={type:'detail'};const lateDetail=module.open(2);project=2;module.resetProject();held.reject(Error('Old project error'));await lateDetail;
check('late_detail_errors_do_not_leak_into_new_project',()=>assert.equal(nodes.reportMessage.textContent,''));
await reset();held={type:'list'};const lateList=module.reload();project=2;module.resetProject();held.resolve({items:[item(1,'documentary','updated')],can_write:true,can_publish:true,published_count:1});await lateList;
check('late_list_cannot_restore_old_project_capabilities',()=>{assert.equal(nodes.reportList.children.length,0);assert(nodes.reportForm.hidden);});
await reset();held={type:'write'};const lateSave=nodes.reportForm.listeners.submit({preventDefault(){}});check('save_in_progress_blocks_project_switch_and_editing',()=>{assert.equal(module.canLeaveProject(),false);assert(nodes.reportNote.disabled);});const count=requests.length;project=2;module.resetProject();held.resolve({id:1,version:3});await lateSave;
check('late_save_never_reloads_report_from_new_project',()=>assert.equal(requests.length,count));
await reset();resetOnBlob=true;const total=downloads.length;await nodes.reportExport.onclick();check('project_reset_during_blob_creation_discards_download',()=>assert.equal(downloads.length,total));
await reset();allow=false;await module.reload();check('reader_has_no_creation_or_release_controls',()=>{assert(nodes.reportForm.hidden);assert(nodes.reportPublish.hidden);assert(nodes.reportNew.hidden);assert.equal(nodes.reportBody.children.length,0);});
check('only_same_origin_project_requests',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases:tests,browser_visual_acceptance:false}));
