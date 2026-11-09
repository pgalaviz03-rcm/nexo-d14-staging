import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.style={};this.listeners={};this.checked=false;this.hidden=false;}
 set innerHTML(v){throw Error('Untrusted HTML rendering');}
 append(...xs){for(const x of xs){x.parent=this;this.children.push(x);}}replaceChildren(...xs){this.children=[];this.append(...xs);}
 addEventListener(k,f){this.listeners[k]=f;}reset(){}focus(){this.focused=true;}scrollIntoView(){}remove(){this.parent.children=this.parent.children.filter(x=>x!==this);}
}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};
const tests=[];const check=(name,fn)=>{fn();tests.push(name);};
let project=1,canManage=true,confirmed=true,lastBody=null,late=null,saved=0,openedPulse=null;
let rows=[{id:1,name:'Actor <script>literal</script>',kind:'primary',active:true,is_demo:false,version:1,profile_version:0,
 public_role:'Representante público',organization:'Institución',territory:'Territorio de prueba',description:'Texto <b>literal</b>',aliases:['Alias público'],
 channels:[{network:'x',url:'https://x.com/public_fixture',external_id:'',review:'unreviewed',enabled:true}],mentions_in_archive:12,account_snapshots:0,last_snapshot_at:null},
 {id:2,name:'Actor B',kind:'comparator',active:true,is_demo:false,version:1,profile_version:0,public_role:'',organization:'',territory:'',description:'',aliases:[],channels:[],mentions_in_archive:0,account_snapshots:0,last_snapshot_at:null}];
const requests=[];
async function api(path,opts={}){requests.push({path,opts});assert(path.startsWith('/api/projects/'+project+'/actors'));
 if(!opts.method){if(late)return new Promise(r=>late.resolve=r);return {project:{id:project,name:'Proyecto de prueba'},items:structuredClone(rows),can_manage:canManage,truncated:false};}
 lastBody=JSON.parse(opts.body);const id=Number(path.match(/\/actors\/(\d+)/)?.[1]);
 if(path.endsWith('/state')){rows.find(x=>x.id===id).active=lastBody.active;rows.find(x=>x.id===id).version++;return {version:2};}
 if(path.endsWith('/primary')){for(const r of rows)r.kind=r.id===id?'primary':'comparator';return {id,version:2};}
 if(opts.method==='PUT'){const r=rows.find(x=>x.id===id);Object.assign(r,lastBody);r.version++;r.profile_version++;return {id,version:r.version};}
 const row={...structuredClone(rows[1]),...lastBody,id:3,version:1,profile_version:1};rows.push(row);return {id:3,version:1,profile_version:1};
}
const window={};vm.runInNewContext(fs.readFileSync(new URL('actors.js',base),'utf8'),{window,document:{createElement:tag=>new Element(tag)},confirm:()=>confirmed});
const module=window.NexoActors.install({api,byId,getProject:()=>project,onChanged:async()=>{saved++;},onOpenPulse:id=>{openedPulse=id;}});
nodes.actorStatusFilter.value='active';await module.reload();
check('project_directory_counts',()=>{assert.equal(nodes.actorsActiveCount.textContent,'2');assert.equal(nodes.actorsChannelCount.textContent,'1');assert.equal(nodes.actorsReviewCount.textContent,'1');});
check('literal_actor_names',()=>assert.equal(nodes.actorsContent.children[0].children.find(x=>x.tagName==='h3').textContent,'Actor <script>literal</script>'));
const actions=card=>card.children.find(x=>x.className==='actions');
actions(nodes.actorsContent.children[0]).children[0].onclick();
check('public_dossier_and_literal_text',()=>{assert.equal(nodes.actorDetail.hidden,false);assert(nodes.actorDetail.children.some(x=>x.textContent==='Texto <b>literal</b>'));});
nodes.actorDetail.children.at(-1).children[0].onclick();check('same_actor_opened_in_pulse',()=>assert.equal(openedPulse,1));
nodes.actorSearch.value='alias público';nodes.actorSearch.listeners.input();check('searches_aliases',()=>assert.equal(nodes.actorsContent.children.length,1));
nodes.actorSearch.value='';nodes.actorSearch.listeners.input();
nodes.settingsActors.children[0].children[1].children[0].onclick();nodes.actorName.value='Nombre revisado';nodes.actorForm.listeners.input();confirmed=false;
check('unsaved_project_switch_guard',()=>assert.equal(module.canLeaveProject(),false));
await module.reload();check('refresh_preserves_unsaved_editor',()=>assert.equal(nodes.actorName.value,'Nombre revisado'));
confirmed=true;await nodes.actorForm.onsubmit({preventDefault(){}});
check('optimistic_shared_actor_edit',()=>{assert.equal(lastBody.expected_actor_version,1);assert.equal(lastBody.expected_profile_version,0);assert.equal(rows[0].name,'Nombre revisado');assert.equal(saved,1);});
check('no_scope_or_secret_fields_submitted',()=>{assert(!('project_id' in lastBody));assert(!('user_id' in lastBody));assert(!('api_key' in lastBody));});
nodes.actorAdd.onclick();nodes.actorName.value='Actor nuevo';nodes.actorAliases.value='Nombre público alternativo';nodes.actorKind.value='comparator';nodes.actorAddChannel.onclick();
const channel=nodes.actorChannels.children[0];channel.children[0].children[0].value='facebook';channel.children[1].children[0].value='https://facebook.com/public_fixture';
await nodes.actorForm.onsubmit({preventDefault(){}});
check('creates_dossier_with_public_references',()=>{assert.equal(lastBody.name,'Actor nuevo');assert.equal(lastBody.channels[0].url,'https://facebook.com/public_fixture');assert.equal(lastBody.channels[0].review,'unreviewed');});
let second=nodes.settingsActors.children.find(x=>x.children[0].children.some(n=>n.textContent==='Actor B'));
await second.children[1].children.find(x=>x.textContent==='Hacer principal').onclick();
check('primary_switch_includes_previous_version',()=>{assert.equal(lastBody.previous_primary_id,1);assert.equal(lastBody.previous_primary_version,2);assert.equal(rows[1].kind,'primary');});
second=nodes.settingsActors.children.find(x=>x.children[0].children.some(n=>n.textContent==='Actor B'));
await second.children[1].children.find(x=>x.textContent==='Archivar').onclick();
check('archive_is_explicit_state_change',()=>{assert.equal(lastBody.active,false);assert.equal(rows[1].active,false);});
nodes.actorStatusFilter.value='archived';nodes.actorStatusFilter.onchange();check('archived_filter',()=>assert.equal(nodes.actorsContent.children.length,1));
canManage=false;await module.reload();check('reader_has_no_management_controls',()=>{assert.equal(nodes.actorAdd.hidden,true);assert.equal(nodes.actorEditor.hidden,true);assert.equal(actions(nodes.actorsContent.children[0]).children.length,1);});
late={};const pending=module.reload();project=2;module.resetProject();late.resolve({items:rows,can_manage:true});await pending;
check('late_other_project_response_discarded',()=>{assert.equal(nodes.actorsContent.children.length,0);assert.equal(nodes.actorDetail.hidden,true);assert.equal(nodes.actorName.value,'');});
check('project_fields_and_permissions_cleared',()=>{assert.equal(nodes.actorChannels.children.length,0);assert.equal(nodes.actorAdd.hidden,true);assert.equal(nodes.actorSearch.value,'');});
check('no_external_provider_calls',()=>assert(requests.every(x=>x.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases:tests,browser_visual_acceptance:false}));
