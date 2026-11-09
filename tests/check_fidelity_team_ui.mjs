import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
let downloads=[];
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.value='';this.style={};this.attributes={};this.hidden=false;this.files=[];this.disabled=false;}
 append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(k,v){this.attributes[k]=v;}click(){downloads.push(this.download);}
 set innerHTML(v){throw Error('Unsafe HTML');}
}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()]));
const byId=id=>{assert(nodes[id],id);return nodes[id];},text=n=>[n.textContent,...n.children.map(text)].join(' ');
let project=1,owner=true,pending=null,requests=[];
const row={member_id:1,name:'Colaborador <script>literal</script>',networks:['facebook'],reaction_posts:2,comment_posts:1,comment_events:null,participated_posts:2,eligible_posts:4,participation_percent:50,last_observed:'2026-10-20T12:00:00Z'};
const fixture={summary:{members:1,members_with_records:1},rows:[row],community:{reactions:20,comments:10,shares:null}};
const roster={items:[{id:1,name:'Colaborador',profiles:{facebook:'equipo.uno'},active:true},{id:2,name:'Inactivo',profiles:{facebook:'inactive'},active:false}]};
const scope={actor_id:1,window:{start:'2026-10-01T00:00:00Z',end:'2026-10-21T00:00:00Z'},network:'all',accounts:[{network:'facebook',url:'https://facebook.com/fixture'}]};
const api=async(path,options={})=>{requests.push({path,options});if(pending)return new Promise(r=>pending.resolve=r);
 if(path.includes('/profile?'))return {name:row.name,accounts:[{network:'facebook',url:'https://facebook.com/equipo.uno'}],summary:row,actor_name:'Actor de prueba',items:[{network:'facebook',url:'https://facebook.com/fixture/posts/1',text:'Publicación <script>literal</script>',published_at:'2026-10-20T10:00:00Z',reaction_recorded:true,comment_recorded:true,identified_comments:0,last_observed:'2026-10-20T12:00:00Z'}],page:1,page_size:20,total_publications:1};
 if(path.endsWith('/roster'))return structuredClone(roster);
 if(path.endsWith('/template'))return {filename:'NEXO_Equipo_Plantilla.csv',csv_text:'Nombre,Facebook\nEjemplo,ejemplo'};
 if(options.method==='POST')return {inserted:1,updated:0,unchanged:0,duplicates:0};
 return {...structuredClone(fixture),can_manage:owner};};
const window={},document={createElement:t=>new Element(t)};
class MockURL extends URL{static createObjectURL(){return 'blob:test';}static revokeObjectURL(){}}
class FormData{constructor(){this.fields=[];}append(k,v){this.fields.push([k,v]);}}
vm.runInNewContext(fs.readFileSync(new URL('fidelity_team.js',base),'utf8'),{window,document,URL:MockURL,URLSearchParams,TextEncoder,Date,Blob,FormData,setTimeout:f=>f(),confirm:()=>false,console});
const module=window.NexoTeam.install({api,byId,getProject:()=>project}),cases=[],check=(n,f)=>{f();cases.push(n);};
await module.reload(scope);
check('objective_counts_and_unknown_comments',()=>{assert(text(nodes.teamRows).includes('50 %'));assert(text(nodes.teamRows).includes('—'));});
check('literal_names_never_markup',()=>assert(text(nodes.teamRows).includes('<script>literal</script>')));
check('owner_roster_controls_visible',()=>{assert(!nodes.teamManagePanel.hidden);assert.equal(nodes.teamRosterList.children.length,2);});
check('account_selector_ready_after_load',()=>assert.equal(nodes.teamSourceAccount.children.length,1));
check('profile_domain_and_scheme_match',()=>{assert.equal(module.profileKey('facebook','https://instagram.com/equipo.uno'),'');assert.equal(module.profileKey('facebook','http://facebook.com/equipo.uno'),'');assert.equal(module.profileKey('facebook','https://facebook.com/profile.php?id=123'),'id:123');});
const raw={actualizado:'2026-10-20T12:00:00Z',org:[['UNREGISTERED']],team:{private:'IGNORE'},publicaciones:[{red:'fb',cuenta:'https://www.facebook.com/fixture/',url:'https://facebook.com/fixture/posts/1',autores:[
 ['fb','equipo.uno','Different display name','reaccion'],['fb','equipo.uno','Different display name','reaccion'],['fb','equipo.uno','Different display name','comentario'],
 ['fb','UNREGISTERED','Colaborador','comentario'],['fb','inactive','Inactivo','reaccion'],['fb','https://instagram.com/equipo.uno','Colaborador','reaccion'],['ig','equipo.uno','Colaborador','reaccion']
 ]},{red:'fb',cuenta:'https://facebook.com/other',url:'https://facebook.com/other/posts/2',autores:[['fb','equipo.uno','Different display name','reaccion']]}]};
const normalized=module.normalizeAtalaya(raw,scope.accounts[0]);
check('only_exact_active_roster_account',()=>{assert.equal(normalized.body.events.length,2);assert(normalized.body.events.every(e=>e.member_id===1));});
check('dedup_and_comment_presence_not_fabricated_count',()=>assert.deepEqual(Array.from(normalized.body.events,e=>e.kind),['reaction','comment_presence']));
check('unknown_people_and_private_source_fields_not_forwarded',()=>assert(!/UNREGISTERED|IGNORE|Different display name|autores|org/.test(JSON.stringify(normalized.body))));
nodes.teamMemberName.value='Colaborador nuevo';nodes.teamMemberName.oninput();
check('manual_unsaved_entry_guard',()=>assert.equal(module.canLeaveProject(),false));
await nodes.teamMemberForm.onsubmit({preventDefault(){}});
check('manual_requires_registered_network',()=>{assert(nodes.teamMemberStatus.textContent.includes('al menos una cuenta'));assert(!requests.some(r=>r.path.endsWith('/roster/member')));});
nodes.teamMemberFacebook.value='equipo.nuevo';nodes.teamMemberFacebook.oninput();nodes.teamMemberCode.value='N03';nodes.teamMemberCode.oninput();
await nodes.teamMemberForm.onsubmit({preventDefault(){}});
check('manual_owner_sends_literal_explicit_account',()=>{const r=requests.find(r=>r.path.endsWith('/roster/member'));const p=JSON.parse(r.options.body);assert.equal(p.code,'N03');assert.equal(p.facebook,'equipo.nuevo');assert.equal(r.path,'/api/projects/1/continuity/team/roster/member');assert.equal(nodes.teamMemberName.value,'');});
nodes.teamCommunityTab.onclick();check('community_aggregate_only',()=>{assert(nodes.teamTablePanel.hidden);assert(!nodes.teamCommunityPanel.hidden);assert.equal(nodes.teamCommunity.children.length,3);assert(!text(nodes.teamCommunity).includes('Colaborador'));});nodes.teamTab.onclick();
nodes.teamSourceAccount.value=scope.accounts[0].url;nodes.teamSourceFile.files=[{size:200,text:async()=>JSON.stringify(raw)}];nodes.teamSourceFile.onchange();
check('file_dirty_guard',()=>assert.equal(module.canLeaveProject(),false));
await nodes.teamSourceForm.onsubmit({preventDefault(){}});
check('events_current_project_only',()=>{const r=requests.find(r=>r.path.endsWith('/events'));assert.equal(r.path,'/api/projects/1/continuity/team/events');assert.equal(JSON.parse(r.options.body).events.length,2);});
nodes.teamRosterFile.files=[{size:100,name:'equipo.xlsx'}];nodes.teamRosterFile.onchange();await nodes.teamRosterForm.onsubmit({preventDefault(){}});
check('roster_upload_uses_multipart',()=>assert(requests.find(r=>r.path.endsWith('/roster/import')).options.body instanceof FormData));
await nodes.teamTemplate.onclick();check('download_template',()=>assert.equal(downloads.at(-1),'NEXO_Equipo_Plantilla.csv'));
owner=false;const before=requests.filter(r=>r.path.endsWith('/roster')).length;await module.reload(scope);
check('reader_no_roster_or_import_management',()=>{assert(nodes.teamManagePanel.hidden);assert.equal(requests.filter(r=>r.path.endsWith('/roster')).length,before);});
const writes=requests.filter(r=>r.options.method).length;await nodes.teamRosterForm.onsubmit({preventDefault(){}});await nodes.teamMemberForm.onsubmit({preventDefault(){}});check('reader_controller_refuses_writes',()=>assert.equal(requests.filter(r=>r.options.method).length,writes));
await nodes.teamRows.children[0].children[1].children[0].onclick();
check('registered_member_profile_is_readable_by_consultant',()=>{assert(!nodes.teamProfilePanel.hidden);assert.equal(nodes.teamProfileName.textContent,row.name);assert.equal(nodes.teamProfileAccounts.children.length,1);assert(text(nodes.teamProfileItems).includes('Comentario registrado'));});
check('profile_publication_text_is_literal',()=>assert(text(nodes.teamProfileItems).includes('<script>literal</script>')));
nodes.teamProfileClose.onclick();check('profile_can_be_closed',()=>assert(nodes.teamProfilePanel.hidden));
pending={};const lateProfile=nodes.teamRows.children[0].children[1].children[0].onclick();project=2;module.reset();pending.resolve({name:'Foreign late profile'});await lateProfile;pending=null;
check('late_member_profile_does_not_cross_projects',()=>{assert(nodes.teamProfilePanel.hidden);assert.equal(nodes.teamProfileName.textContent,'');});
project=1;await module.reload(scope);
pending={};const late=module.reload(scope);project=2;module.reset();pending.resolve({...fixture,can_manage:true});await late;
check('stale_response_cannot_cross_project',()=>{assert.equal(nodes.teamMemberName.value,'');assert.equal(nodes.teamRows.children.length,0);assert(nodes.teamManagePanel.hidden);assert.equal(nodes.teamPager.textContent,'');});pending=null;
project=1;owner=true;await module.reload(scope);nodes.teamSourceAccount.value=scope.accounts[0].url;
let finish;nodes.teamSourceFile.files=[{size:100,text:()=>new Promise(r=>finish=r)}];nodes.teamSourceFile.onchange();const beforeWrites=requests.filter(r=>r.options.method==='POST').length;
const writing=nodes.teamSourceForm.onsubmit({preventDefault(){}});project=2;module.reset();finish(JSON.stringify(raw));await writing;
check('late_file_cannot_post_after_project_change',()=>assert.equal(requests.filter(r=>r.options.method==='POST').length,beforeWrites));
check('no_provider_or_network_source_requests',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
