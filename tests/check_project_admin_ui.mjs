/* Regression: actual nested controllers must load owner controls in empty projects. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.value='';this.style={};this.attributes={};this.hidden=false;this.files=[];this.disabled=false;this.listeners={};}
 append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(k,v){this.attributes[k]=v;}click(){}reset(){}focus(){}scrollIntoView(){}addEventListener(k,f){this.listeners[k]=f;}
 set innerHTML(v){throw Error('Unsafe HTML');}
}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()]));
const byId=id=>{assert(nodes[id],id);return nodes[id];},text=n=>[n.textContent,...n.children.map(text)].join(' ');
let project=1,owner=true,requests=[],deferred=null;
const refs=pid=>actors[pid].length?[{network:'facebook',url:'https://facebook.com/project.'+pid}]:[];
const actors={1:[{id:11,name:'Actor del primer proyecto',kind:'primary',active:true,channels:[],aliases:[],mentions_in_archive:0,account_snapshots:0}],2:[],3:[]};
const teams={1:[{id:1,name:'Equipo del primer proyecto',profiles:{facebook:'first.team'},active:true}],2:[],3:[]};
const period={start:'2026-10-20T00:00:00Z',end:'2026-10-27T00:00:00Z'};
const empty={participants:null,returning:null,new:null,return_rate:null,retention_rate:null,status:'pending'};
function dashboard(pid){return{project_id:pid,actors:actors[pid],selected_actor_id:actors[pid][0]?.id??null,accounts:refs(pid),selected_account:null,
 measurements:[],selected_measurement:'',window:period,current:empty,previous:empty,return_rate_change_pp:null,baseline_consistent:true,series:[],can_import:owner};}
function publications(pid){return{project_id:pid,actor_id:actors[pid][0]?.id??null,actor_name:actors[pid][0]?.name??'',registered_accounts:refs(pid),window:period,
 summary:{publications:null,engagement_rate:null,interactions:null,followers:null,mentions:null,account_count:refs(pid).length},publications:[],mentions:[],source_kind:'empty',can_import:owner};}
function teamPacket(pid){return{project_id:pid,actor_id:actors[pid][0]?.id??null,can_manage:owner,summary:{members:teams[pid].length,members_with_records:0},
 rows:teams[pid].map(m=>({member_id:m.id,name:m.name,networks:['facebook'],reaction_posts:0,comment_posts:0,comment_events:null,participated_posts:0,eligible_posts:0,participation_percent:null,last_observed:null})),community:{reactions:null,comments:null,shares:null}};}
async function api(path,options={}){
 requests.push({path,options});const pid=Number(path.match(/^\/api\/projects\/(\d+)/)?.[1]);assert(pid>0);assert(!path.includes('actor_id=null')&&!path.includes('actor_id=undefined'));
 if(deferred&&path.includes('/continuity/activity'))return new Promise(r=>deferred.resolve=r);
 if(path.endsWith('/actors')){if(options.method==='POST'){const body=JSON.parse(options.body);actors[pid].push({...actors[1][0],...body,id:pid*11});return{id:pid*11};}return{project:{id:pid,name:'Proyecto '+pid},items:structuredClone(actors[pid]),can_manage:owner};}
 if(path.endsWith('/roster/member')){const body=JSON.parse(options.body);teams[pid].push({id:pid*100,name:body.name,profiles:{facebook:body.facebook},active:true});return{inserted:1};}
 if(path.endsWith('/roster'))return{items:structuredClone(teams[pid])};
 if(path.includes('/continuity/team?'))return teamPacket(pid);
 if(path.includes('/continuity/activity?'))return publications(pid);
 if(path.includes('/continuity?'))return dashboard(pid);
 throw Error('Unexpected local route: '+path);
}
const window={},document={createElement:t=>new Element(t)},context={window,document,URL,URLSearchParams,Date,Intl,Blob,TextEncoder,setTimeout:f=>f(),confirm:()=>false};
for(const script of ['fidelity_team.js','fidelity.js','continuity.js','actors.js'])vm.runInNewContext(fs.readFileSync(new URL(script,base),'utf8'),context);
const module=window.NexoContinuity.install({api,byId,getProject:()=>project,onConfigure:()=>{}});
const actorsModule=window.NexoActors.install({api,byId,getProject:()=>project,onChanged:()=>module.reload(),onOpenPulse:()=>{}});
const settle=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
const cases=[],check=(n,f)=>{f();cases.push(n);};nodes.continuityPeriod.value='7';nodes.continuityNetwork.value='all';nodes.actorStatusFilter.value='active';
await module.reload();await settle();
check('existing_project_owner_controls_and_team',()=>{assert(!nodes.teamManagePanel.hidden);assert(text(nodes.teamRows).includes('Equipo del primer proyecto'));});
nodes.continuityPeriod.value='custom';nodes.continuityFrom.value='';nodes.continuityTo.value='';nodes.continuityNetwork.value='instagram';await module.focusActor(11);await settle();check('configuration_setup_ignores_incomplete_operational_filters',()=>{assert(!nodes.teamManagePanel.hidden);assert.equal(nodes.continuityNetwork.value,'all');assert(requests.at(-1).path.startsWith('/api/projects/1/'));});
project=2;module.resetProject();actorsModule.resetProject();await module.reload();await actorsModule.reload();await settle();
check('empty_project_is_not_mistaken_for_reader',()=>{assert(!nodes.teamManagePanel.hidden);assert(!nodes.actorAdd.hidden);assert.equal(nodes.fidelityAccessLabel.textContent,'Administración del proyecto');});
check('both_nested_dashboards_requested_without_actor',()=>{assert(requests.some(r=>r.path.includes('/2/continuity/activity?')&&r.path.includes('actor_id=0')));assert(requests.some(r=>r.path.includes('/2/continuity/team?')&&r.path.includes('actor_id=0')));});
check('previous_project_identity_not_reused',()=>{assert(!text(nodes.teamRows).includes('primer proyecto'));assert(!text(nodes.fidelityAccounts).includes('primer proyecto'));assert.equal(nodes.teamRosterList.children.length,0);});
check('account_readiness_is_separate_from_team_permission',()=>{assert(nodes.teamSourceForm.hidden);assert(!nodes.teamAccountSetup.hidden);assert(nodes.fidelityImportPanel.hidden);assert(!nodes.teamManagePanel.hidden);});
nodes.teamMemberName.value='Integrante del cliente nuevo';nodes.teamMemberFacebook.value='new.team';nodes.teamMemberName.oninput();
await nodes.teamMemberForm.onsubmit({preventDefault(){}});await settle();
check('manual_team_setup_works_before_first_actor',()=>{assert.equal(teams[2].length,1);assert.equal(teams[1].length,1);assert(text(nodes.teamRows).includes('Integrante del cliente nuevo'));assert(requests.some(r=>r.path==='/api/projects/2/continuity/team/roster/member'));});
nodes.actorAdd.onclick();nodes.actorName.value='Actor del cliente nuevo';nodes.actorKind.value='primary';await nodes.actorForm.onsubmit({preventDefault(){}});await settle();
check('first_actor_can_be_created_and_team_is_preserved',()=>{assert.equal(actors[2].length,1);assert(!nodes.teamManagePanel.hidden);assert(text(nodes.teamRows).includes('Integrante del cliente nuevo'));assert(!nodes.teamSourceForm.hidden);assert(nodes.teamAccountSetup.hidden);});
project=1;module.resetProject();actorsModule.resetProject();await module.reload();await settle();
check('switch_back_preserves_original_project',()=>{assert(!nodes.teamManagePanel.hidden);assert(text(nodes.teamRows).includes('Equipo del primer proyecto'));assert(!text(nodes.teamRows).includes('cliente nuevo'));});
project=3;owner=false;module.resetProject();actorsModule.resetProject();await module.reload();await actorsModule.reload();await settle();
check('reader_in_empty_project_still_has_no_management',()=>{assert(nodes.teamManagePanel.hidden);assert(nodes.actorAdd.hidden);assert.equal(nodes.fidelityAccessLabel.textContent,'Consulta del proyecto');});
const writes=requests.filter(r=>r.options.method).length;await nodes.teamMemberForm.onsubmit({preventDefault(){}});
check('reader_controller_cannot_save_after_switch',()=>assert.equal(requests.filter(r=>r.options.method).length,writes));
owner=true;project=2;module.resetProject();await module.reload();await settle();
deferred={};const pending=module.reload();await settle();project=3;module.resetProject();deferred.resolve(publications(2));await pending;await settle();deferred=null;
check('late_previous_project_cannot_restore_owner_controls',()=>{assert(nodes.teamManagePanel.hidden);assert.equal(nodes.teamRows.children.length,0);});
check('all_requests_stay_local',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
