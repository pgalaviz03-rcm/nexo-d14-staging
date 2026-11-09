/* Unified archive controller with synthetic sources and simulated DOM only. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.style={};this.attributes={};}set innerHTML(v){throw Error('Unsafe HTML');}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}setAttribute(k,v){this.attributes[k]=v;}scrollIntoView(){this.scrolled=true;}click(){if(this.tagName==='a')downloads.push(this.download);}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};
const item={reference:'news:1',kind:'news',title:'Literal <script>title</script>',source:'Source',network:'press',date_basis:'published',at:'2026-10-20T12:00:00Z',url:'https://example.org/source',excerpt:'Source excerpt',preview_status:'stored_excerpt',content_sha256:'fixture'};
const fixture={project_id:1,items:[item],matched_in_scan:1,counts:{news:1,social:0,document:0},sources:[{value:'news:Source',label:'Source'}],actors:[{id:1,name:'Public actor',active:true}],offset:0,page_size:20,has_more:false,filters:{actor_id:0},coverage:{scanned:{news:1},bounded:false,documents_metadata_only:0},can_save_report:true};
let project=1,response=structuredClone(fixture),deferred=null,detailDeferred=null,selectionDeferred=null,requests=[],downloads=[],saved=[],library=0,confirmResult=false,conflict=false;
async function api(path,options={}){requests.push({path,options});assert(path.startsWith('/api/projects/'+project+'/explorer'));
 if(path.endsWith('/reports')){if(conflict)throw Error('Las fuentes cambiaron');return {id:7};}
 if(path.endsWith('/selection')){if(selectionDeferred)return new Promise(r=>selectionDeferred.resolve=r);return {project_id:project,preview_sha256:'a'.repeat(64),citations:[{citation:'news:1',title:item.title,source:item.source,excerpt:item.excerpt}]};}
 if(path.includes('/items/')){if(detailDeferred)return new Promise(r=>detailDeferred.resolve=r);return {...item,project_id:project};}
 if(deferred)return new Promise(r=>deferred.resolve=r);return structuredClone(response);}
const window={};vm.runInNewContext(fs.readFileSync(new URL('explorer.js',base),'utf8'),{window,document:{createElement:t=>new Element(t)},Date,Intl,Blob,Map,URLSearchParams,setTimeout:f=>f(),confirm:()=>confirmResult,URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL(){}}});
const module=window.NexoExplorer.install({api,byId,getProject:()=>project,onSaved:async id=>saved.push(id),onLibrary:()=>library++});
for(const [id,val] of [['explorerKind','all'],['explorerNetwork','all'],['explorerActor','0'],['explorerSource',''],['explorerPeriod','all']])nodes[id].value=val;
const tests=[],check=(name,f)=>{f();tests.push(name);};await module.reload();
check('scanned_matches_not_invented_audience',()=>{assert.equal(nodes.explorerTotal.textContent,'1');assert.equal(nodes.explorerSocial.textContent,'0');});
check('literal_source_titles',()=>assert.equal(nodes.explorerResults.children[0].children[1].textContent,item.title));
check('reading_archive_never_creates_reports',()=>assert(requests.every(r=>!r.options.method)));
nodes.explorerResults.children[0].children[1].onclick();await new Promise(setImmediate);
check('detail_has_source_date_and_hash',()=>{assert.equal(nodes.explorerDetailTitle.textContent,item.title);assert(nodes.explorerDetailMeta.textContent.includes('Publicación'));assert(nodes.explorerDetailHash.textContent.includes('fixture'));assert(nodes.explorerDetail.scrolled);});
const box=()=>nodes.explorerResults.children[0].children[3].children[0];box().checked=true;box().onchange();
check('selection_guard_and_count',()=>{assert.equal(nodes.explorerSelectedCount.textContent,'1');assert.equal(module.canLeaveProject(),false);});
await nodes.explorerPrepare.onclick();check('selection_sends_ids_only',()=>{const body=JSON.parse(requests.find(r=>r.path.endsWith('/selection')).options.body);assert.deepEqual(body,{references:['news:1']});});
nodes.explorerReportTitle.value='Fixture report';nodes.explorerReportNote.value='Keep this note';nodes.explorerReportNote.oninput();conflict=true;await nodes.explorerSaveForm.onsubmit({preventDefault(){}});
check('changed_source_keeps_editorial_note',()=>{assert.equal(nodes.explorerReportNote.value,'Keep this note');assert.equal(saved.length,0);assert(nodes.explorerSelectionStatus.textContent.includes('cambiaron'));});
conflict=false;await nodes.explorerSaveForm.onsubmit({preventDefault(){}});
check('save_includes_preview_hash_and_opens_report',()=>{const b=JSON.parse(requests.find(r=>r.path.endsWith('/reports')).options.body);assert.equal(b.preview_sha256,'a'.repeat(64));assert(!('citations' in b));assert.deepEqual(saved,[7]);assert.equal(module.canLeaveProject(),true);});
nodes.explorerPageExport.onclick();nodes.explorerSelectionDownload.onclick();check('exports_distinguish_page_and_selection',()=>assert.deepEqual(downloads,['NEXO_Explorador_Pagina.json','NEXO_Seleccion_Evidencias.json']));
nodes.explorerLibrary.onclick();check('existing_library_remains_accessible',()=>assert.equal(library,1));
response={...structuredClone(fixture),can_save_report:false};await module.reload();check('reader_can_select_but_save_form_hidden',()=>assert(nodes.explorerSaveForm.hidden));
response=structuredClone(fixture);response.items=[{...item,reference:'document:2',kind:'document',preview_status:'metadata_only'}];await module.reload();check('unverified_document_not_added_as_text_evidence',()=>assert(box().disabled));
response=structuredClone(fixture);await module.reload();selectionDeferred={};const pending=nodes.explorerPrepare.onclick();project=2;module.resetProject();selectionDeferred.resolve({citations:[{title:'Other project'}],preview_sha256:'old'});await pending;selectionDeferred=null;
check('late_selection_cannot_cross_projects',()=>assert.equal(nodes.explorerSelectionPreview.children.length,0));
response=structuredClone(fixture);await module.reload();detailDeferred={};nodes.explorerResults.children[0].children[1].onclick();project=3;module.resetProject();detailDeferred.resolve(item);await new Promise(setImmediate);detailDeferred=null;
check('late_detail_discarded',()=>{assert(nodes.explorerDetail.hidden);assert.equal(nodes.explorerDetailText.textContent,'');});
deferred={};const late=module.reload();project=4;module.resetProject();deferred.resolve(fixture);await late;
check('late_archive_discarded',()=>assert.equal(nodes.explorerResults.children.length,0));
check('project_reset_removes_private_notes_and_selected_sources',()=>{assert.equal(nodes.explorerReportNote.value,'');assert.equal(nodes.explorerSelectedCount.textContent,'0');assert.equal(nodes.explorerChosen.children.length,0);assert(nodes.explorerPageExport.disabled);});
check('same_origin_no_semantic_or_provider_calls',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases:tests,browser_visual_acceptance:false}));

