/* Synthetic controller workflow; no browser, messages, or external provider. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.style={};this.attributes={};}
 set innerHTML(v){throw Error('Unsafe rendering');}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}setAttribute(k,v){this.attributes[k]=v;}click(){if(this.tagName==='a')downloads.push(this.download);}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};
const reading={id:1,actor_id:1,actor_name:'Public <script>literal</script>',name:'Rule literal',metric:'mentions',threshold:3,min_mentions:1,active:true,status:'triggered',value:3,mentions:3,classified:0,classification_coverage:0};
const incident={id:1,actor_id:1,rule_id:1,network:'all',window:{start:'2026-10-19T12:00:00Z',end:'2026-10-20T12:00:00Z'},snapshot:{reading,sources:[{title:'Title <script>literal</script>',url:'https://example.org/public',network:'facebook',published_at:'2026-10-20T11:00:00Z'}],sources_bounded:false},snapshot_sha256:'fixture',created_at:'2026-10-20T13:00:00Z',status:'open',version:0};
const fixture={project_id:1,actors:[{id:1,name:reading.actor_name,active:true}],window:incident.window,network:'all',readings:[reading],incidents:[incident],incidents_bounded:false,incident_limit:200,counts:{open:1,acknowledged:0,resolved:0,dismissed:0},can_review:true,can_manage_rules:true};
let project=1,response=structuredClone(fixture),details={...structuredClone(incident),history:[],can_review:true},deferred=null,detailDeferred=null,confirmResult=false,downloads=[],requests=[],conflict=false;
async function api(path,options={}){requests.push({path,options});assert(path.startsWith('/api/projects/'+project+'/'));
 if(options.method==='POST'&&path.endsWith('/reviews')){if(conflict)throw Error('Otra persona actualizó el incidente');const b=JSON.parse(options.body);details={...details,status:b.status,version:details.version+1,history:[{version:1,previous_status:'open',status:b.status,note:b.note,at:incident.created_at}]};return details;}
 if(options.method==='POST'&&path.endsWith('/evaluate'))return {inserted:1,duplicates:0,evaluable:1};
 if(options.method==='POST'||options.method==='PATCH')return {id:1};
 if(/\/alerts\/1$/.test(path)){if(detailDeferred)return new Promise(r=>detailDeferred.resolve=r);return structuredClone(details);}
 if(deferred)return new Promise(r=>deferred.resolve=r);return structuredClone(response);}
const window={};vm.runInNewContext(fs.readFileSync(new URL('alerts.js',base),'utf8'),{window,document:{createElement:t=>new Element(t)},Date,Intl,Blob,URLSearchParams,setTimeout:f=>f(),confirm:()=>confirmResult,URL:{createObjectURL:()=> 'blob:fixture',revokeObjectURL(){}}});
const module=window.NexoAlerts.install({api,byId,getProject:()=>project});nodes.alertsNetwork.value='all';nodes.alertsActor.value='0';nodes.alertsPeriod.value='1';nodes.alertsState.value='all';
const tests=[],check=(name,f)=>{f();tests.push(name);};
await module.reload();
check('project_incidents_rules_and_counts',()=>{assert.equal(nodes.alertsOpen.textContent,'1');assert.equal(nodes.alertsWaiting.textContent,'0');assert.equal(nodes.alertsContent.children.length,1);});
check('reading_never_registers_incident',()=>assert(requests.every(r=>!r.options.method)));
nodes.alertsContent.children[0].onclick();await new Promise(setImmediate);
check('detail_uses_frozen_evidence_and_literal_text',()=>{assert(nodes.alertsDetailTitle.textContent.includes('<script>'));assert.equal(nodes.alertsDetailSources.children[0].children[0].textContent,'Title <script>literal</script>');assert(nodes.alertsEvidenceCut.textContent.includes('fixture'));});
nodes.alertsExport.onclick();check('evidence_download',()=>assert.equal(downloads.at(-1),'NEXO_Incidente_1.json'));
nodes.alertsNote.value='Unsaved review';nodes.alertsNote.oninput();await module.reload();
check('refresh_preserves_unsaved_review',()=>assert.equal(nodes.alertsNote.value,'Unsaved review'));
check('unsaved_note_prevents_project_switch',()=>assert.equal(module.canLeaveProject(),false));
nodes.alertsNextState.value='resolved';await nodes.alertsReviewForm.onsubmit({preventDefault(){}});
check('review_sends_expected_version_and_no_forged_user',()=>{const b=JSON.parse(requests.find(r=>r.path.endsWith('/reviews')).options.body);assert.equal(b.expected_version,0);assert.equal(b.status,'resolved');assert(!('user_id' in b));assert.equal(nodes.alertsNote.value,'');});
check('saved_history_rendered',()=>assert.equal(nodes.alertsHistory.children[0].children[0].textContent,'Abierta → Resuelta'));
conflict=true;nodes.alertsNote.value='Keep on conflict';nodes.alertsNote.oninput();nodes.alertsNextState.value='open';await nodes.alertsReviewForm.onsubmit({preventDefault(){}});
check('conflict_keeps_note_for_review',()=>{assert.equal(nodes.alertsNote.value,'Keep on conflict');assert(nodes.alertsDetailStatus.textContent.includes('Otra persona'));});conflict=false;
await nodes.alertsEvaluate.onclick();check('evaluate_is_explicit_and_uses_displayed_cut',()=>{const b=JSON.parse(requests.find(r=>r.path.endsWith('/evaluate')).options.body);assert.equal(b.end,fixture.window.end);assert.equal(b.network,'all');});
nodes.alertsRuleActor.value='1';nodes.alertsRuleName.value='Threshold';nodes.alertsRuleMetric.value='mentions';nodes.alertsRuleThreshold.value='20';nodes.alertsRuleMin.value='20';nodes.alertsRuleName.oninput();
await nodes.alertsRuleForm.onsubmit({preventDefault(){}});check('rules_share_pulse_store',()=>assert(requests.some(r=>r.path==='/api/projects/1/pulse/rules'&&r.options.method==='POST')));
response={...structuredClone(fixture),can_manage_rules:false,can_review:false};module.resetProject();nodes.alertsNetwork.value='all';nodes.alertsState.value='all';nodes.alertsPeriod.value='1';await module.reload();
check('reader_cannot_evaluate_or_manage_rules',()=>{assert(nodes.alertsEvaluate.hidden);assert(nodes.alertsRulePanel.hidden);});
details.can_review=false;nodes.alertsContent.children[0].onclick();await new Promise(setImmediate);check('reader_review_controls_hidden',()=>assert(nodes.alertsReviewForm.hidden));
detailDeferred={};nodes.alertsContent.children[0].onclick();project=2;module.resetProject();detailDeferred.resolve({...details,can_review:true});await new Promise(setImmediate);detailDeferred=null;
check('late_detail_cannot_leak_across_projects',()=>{assert(nodes.alertsDetail.hidden);assert.equal(nodes.alertsDetailTitle.textContent,'');assert.equal(nodes.alertsHistory.children.length,0);});
deferred={};const late=module.reload();project=3;module.resetProject();deferred.resolve(fixture);await late;
check('late_dashboard_cannot_leak_across_projects',()=>assert.equal(nodes.alertsContent.children.length,0));
check('project_reset_clears_private_fields_and_capabilities',()=>{assert.equal(nodes.alertsNote.value,'');assert.equal(nodes.alertsRuleActor.children.length,0);assert(nodes.alertsExport.disabled);assert(nodes.alertsRulePanel.hidden);});
check('same_origin_calls_no_delivery_requests',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/')&&!r.path.includes('notify'))));
console.log(JSON.stringify({passed:true,cases:tests,browser_visual_acceptance:false}));
