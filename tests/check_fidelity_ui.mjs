import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.value='';this.style={};this.attributes={};this.hidden=false;this.files=[];this.disabled=false;}
 append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(k,v){this.attributes[k]=v;}click(){downloads.push(this.download);}
 set innerHTML(v){throw Error('Unsafe HTML');}
}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()]));
const byId=id=>{assert(nodes[id],id);return nodes[id];},text=n=>[n.textContent,...n.children.map(text)].join(' ');
let project=1,canImport=true,pending=null,requests=[],downloads=[],blobs=[];
const fixture={project_id:1,actor_id:1,actor_name:'Cuenta de muestra',registered_accounts:[{network:'facebook',url:'https://facebook.com/fixture'}],
 accounts:[{network:'facebook',url:'https://facebook.com/fixture',followers:100}],window:{start:'2026-10-01T00:00:00Z',end:'2026-10-08T00:00:00Z'},
 summary:{publications:1,interactions:15,followers:100,engagement_rate:15,mentions:0,account_count:1},mentions:[],publications:[
 {url:'https://facebook.com/fixture/posts/1',published_at:'2026-10-07T12:00:00Z',text:'Literal <img onerror=x>',network:'facebook',reactions:10,comments:5,shares:null,interactions:15,engagement_rate:15,partial:true}],
 source_kind:'atalaya_import',latest_capture:'2026-10-08T00:00:00Z',partial_counters:true,mentions_scope:'actor'};
const scope={selected_actor_id:1,window:fixture.window,accounts:fixture.registered_accounts};
const api=async(path,options={})=>{requests.push({path,options});if(pending)return new Promise(r=>pending.resolve=r);return options.method==='POST'?{inserted:1,duplicates:0}:{...structuredClone(fixture),can_import:canImport};};
const window={},document={createElement:t=>new Element(t)};
class MockURL extends URL{static createObjectURL(b){blobs.push(b);return 'blob:fixture';}static revokeObjectURL(){}}
vm.runInNewContext(fs.readFileSync(new URL('fidelity.js',base),'utf8'),{window,document,URL:MockURL,URLSearchParams,TextEncoder,Date,Blob,setTimeout:f=>f(),confirm:()=>false,console});
const module=window.NexoFidelity.install({api,byId,getProject:()=>project});nodes.continuityNetwork.value='all';const cases=[],check=(n,f)=>{f();cases.push(n);};
await module.reload(scope);
check('observed_counters_and_rate',()=>{assert.equal(nodes.fidelityPosts.textContent,'1');assert.equal(nodes.fidelityEngagement.textContent,'15 %');});
check('source_and_missing_coverage_explicit',()=>{assert(text(nodes.fidelityProvenance).includes('Atalaya'));assert(text(nodes.fidelityQuality).includes('ausentes'));});
check('public_text_never_interpreted_as_markup',()=>assert(text(nodes.fidelityRows).includes('<img onerror=x>')));
check('all_accounts_links_and_one_page',()=>{assert.equal(nodes.fidelityAccounts.children.length,1);assert(nodes.fidelityNext.disabled);});
nodes.fidelityMentionsTab.onclick();check('mentions_tab_independent',()=>assert(text(nodes.fidelityRows).includes('Sin registros')));nodes.fidelityPublicationsTab.onclick();
const unsafe={actualizado:'2026-10-08T00:00:00Z',org:[['PRIVATE']],team:{private:true},publicaciones:[
 {url:'https://facebook.com/fixture/posts/1',red:'facebook',cuenta:'https://www.facebook.com/fixture/',fecha:'2026-10-07T12:00:00Z',texto:'Publicación',reacciones:-1,comentarios:5,compartidos:null,seguidores:100,autores:[['PRIVATE']]},
 {url:'https://facebook.com/other/posts/2',red:'facebook',cuenta:'https://facebook.com/other',fecha:'2026-10-07T12:00:00Z'}]};
const normalized=module.normalize(unsafe,scope.accounts[0]);
check('only_selected_account_publications',()=>assert.equal(normalized.publications.length,1));
check('participant_lists_never_in_outgoing_payload',()=>assert(!/PRIVATE|autores|org|team/.test(JSON.stringify(normalized))));
check('negative_sentinel_preserves_unknown',()=>assert.equal(normalized.publications[0].reactions,null));
nodes.fidelityImportPanel.ontoggle();nodes.fidelityImportAccount.value='https://facebook.com/fixture';
nodes.fidelityFile.files=[{size:100,text:async()=>JSON.stringify(unsafe)}];nodes.fidelityFile.onchange();
check('unsaved_import_prevents_project_switch',()=>assert.equal(module.canLeaveProject(),false));
await nodes.fidelityImportForm.onsubmit({preventDefault(){}});
check('import_current_project_only_and_no_identifiers',()=>{const r=requests.find(r=>r.options.method==='POST');assert.equal(r.path,'/api/projects/1/continuity/atalaya/import');assert(!r.options.body.includes('PRIVATE'));});
canImport=false;await module.reload(scope);check('reader_has_no_import',()=>assert(nodes.fidelityImportPanel.hidden));
nodes.fidelityDownload.onclick();check('download_is_authorized_cut',()=>assert.equal(downloads.at(-1),'NEXO_Fidelidad_Corte.json'));
pending={};const late=module.reload(scope);project=2;module.reset();pending.resolve({...fixture,can_import:true});await late;
check('late_response_cannot_cross_projects',()=>assert.equal(nodes.fidelityPosts.textContent,'—'));pending=null;
project=1;canImport=true;await module.reload(scope);nodes.fidelityImportPanel.ontoggle();nodes.fidelityImportAccount.value='https://facebook.com/fixture';
let finish;nodes.fidelityFile.files=[{size:100,text:()=>new Promise(r=>finish=r)}];nodes.fidelityFile.onchange();const before=requests.filter(r=>r.options.method==='POST').length;
const writing=nodes.fidelityImportForm.onsubmit({preventDefault(){}});project=2;module.reset();finish(JSON.stringify(unsafe));await writing;
check('late_file_read_cannot_submit_after_project_change',()=>assert.equal(requests.filter(r=>r.options.method==='POST').length,before));
check('no_provider_requests',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
