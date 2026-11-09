/* Isolated controller test: fabricated accounts/counters only, no browser. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.style={};this.listeners={};this.files=[];this.attributes={};this.hidden=false;}
 set innerHTML(v){throw Error('Untrusted HTML rendering');}append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}
 setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,f){this.listeners[k]=f;}click(){if(this.tagName==='a')downloads.push({name:this.download,url:this.href});}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};
const current={posts:3,views:200,impressions:250,reach:null,interactions:0},previous={posts:1,views:100,impressions:100,reach:null,interactions:0};
const account={actor_id:1,actor_name:'Actor <script>literal</script>',network:'facebook',url:'https://facebook.com/public_fixture',registered:true,reference_review:'unreviewed',followers:100,
 followers_as_of:'2026-10-19T23:00:00+00:00',followers_change:{absolute:10,percent:11.11},followers_baseline_at:'2026-10-12T00:00:00+00:00',current,previous,
 changes:{interactions:{absolute:0,percent:null}},activity_captured_at:'2026-10-20T00:30:00+00:00',series:[{at:'2026-10-14T00:00:00+00:00',followers:90},{at:'2026-10-19T23:00:00+00:00',followers:100}],interactions_per_100_followers:0,status:'available'};
const fixture={project_id:1,selected_actor_id:1,actors:[{id:1,name:account.actor_name,kind:'primary'},{id:2,name:'Actor B',kind:'comparator'}],network:'all',
 window:{start:'2026-10-13T00:00:00+00:00',end:'2026-10-20T00:00:00+00:00'},previous_window:{start:'2026-10-06T00:00:00+00:00',end:'2026-10-13T00:00:00+00:00'},
 accounts:[account],selected_account:account,comparison_network:'facebook',comparison:[{actor_id:1,actor_name:account.actor_name,kind:'primary',account},{actor_id:2,actor_name:'Actor B',kind:'comparator',account:null}],
 can_import:true,coverage_bounded:false,query_limit_per_actor:1000,accounts_limit_per_actor:20};
let project=1,response=structuredClone(fixture),deferred=null,readDeferred=null,canConfirm=false,opened=0,blobs=[],downloads=[],requests=[];
async function api(path,options={}){requests.push({path,options});assert(path.startsWith('/api/projects/'+project+'/networks'));
 if(options.method==='POST'){assert(!('project_id' in JSON.parse(options.body)));return {inserted:1,duplicates:0};}
 if(deferred)return new Promise(r=>deferred.resolve=r);return structuredClone(response);}
const window={};vm.runInNewContext(fs.readFileSync(new URL('networks.js',base),'utf8'),{window,document:{createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)},
 URLSearchParams,URL:{createObjectURL:b=>{blobs.push(b);return 'blob:synthetic';},revokeObjectURL(){}},Blob,Date,Intl,setTimeout:f=>f(),confirm:()=>canConfirm});
const module=window.NexoNetworks.install({api,byId,getProject:()=>project,onConfigure:()=>opened++});nodes.networksNetwork.value='all';nodes.networksPeriod.value='7';
const tests=[],check=(name,fn)=>{fn();tests.push(name);};
await module.reload();
check('account_scope_and_source_numbers',()=>{assert.equal(nodes.networksFollowers.textContent,'100');assert(nodes.networksScope.textContent.includes('Actor <script>literal</script>'));});
check('zero_is_not_missing',()=>{assert.equal(nodes.networksInteractions.textContent,'0');assert.equal(nodes.networksReach.textContent,'—');});
check('chart_uses_observed_points',()=>{const svg=nodes.networksChart.children[0];assert.equal(svg.tagName,'svg');assert.equal(svg.children.filter(x=>x.tagName==='circle').length,2);});
check('comparison_includes_unknown_comparator_without_zeros',()=>{const rows=nodes.networksComparison.children[0].children[1].children;assert.equal(rows.length,2);assert.equal(rows[1].children[1].textContent,'—');});
check('follower_dates_are_visible_in_comparison',()=>assert(nodes.networksComparison.children[0].children[1].children[0].children[1].children.some(n=>n.tagName==='small')));
nodes.networksConfigure.onclick();check('configure_opens_actor_directory',()=>assert.equal(opened,1));
nodes.networksExport.onclick();check('export_preserves_cut_and_source_values',()=>assert.equal(downloads.at(-1).name,'NEXO_Redes_Corte.json'));
nodes.networksTemplate.onclick();const template=JSON.parse(await blobs.at(-1).text());
check('template_has_real_scope_and_null_metrics',()=>{assert.equal(template.items[0].actor_id,1);assert.equal(template.items[0].followers,null);assert.equal(template.items[0].metrics_from,fixture.window.start);});
nodes.networksActor.value='2';nodes.networksActor.onchange();await new Promise(setImmediate);check('actor_filter_sent_to_project_api',()=>assert(requests.at(-1).path.includes('actor_id=2')));
response={...structuredClone(fixture),can_import:false};await module.reload();check('reader_import_controls_hidden',()=>assert.equal(nodes.networksImportPanel.hidden,true));
response=structuredClone(fixture);response.accounts[0].followers=null;response.selected_account.followers=null;response.selected_account.series=[];await module.reload();
check('pending_data_never_becomes_fake_series',()=>{assert.equal(nodes.networksFollowers.textContent,'—');assert.equal(nodes.networksChart.children[0].tagName,'p');});
response=structuredClone(fixture);await module.reload();nodes.networksFile.files=[{size:20,text:async()=>JSON.stringify({provider:'manual',items:[]})}];nodes.networksFile.onchange();
check('unsaved_import_project_guard',()=>assert.equal(module.canLeaveProject(),false));
await nodes.networksImportForm.onsubmit({preventDefault(){}});check('offline_import_targets_current_project',()=>{assert(requests.some(x=>x.options.method==='POST'&&x.path.endsWith('/captures')));assert(nodes.networksImportStatus.textContent.includes('1 capturas'));});
let finish;nodes.networksFile.files=[{size:20,text:()=>new Promise(r=>finish=r)}];nodes.networksFile.onchange();const pending=nodes.networksImportForm.onsubmit({preventDefault(){}});
const before=requests.filter(x=>x.options.method==='POST').length;project=2;module.resetProject();finish('{}');await pending;
check('late_file_read_never_imports_into_new_project',()=>assert.equal(requests.filter(x=>x.options.method==='POST').length,before));
deferred={};const late=module.reload();project=3;module.resetProject();deferred.resolve(fixture);await late;
check('late_project_response_discarded',()=>{assert.equal(nodes.networksContent.children.length,0);assert.equal(nodes.networksFollowers.textContent,'—');});
check('project_reset_clears_inputs_and_privileges',()=>{assert.equal(nodes.networksActor.children.length,0);assert.equal(nodes.networksFile.value,'');assert.equal(nodes.networksImportPanel.hidden,true);assert.equal(nodes.networksExport.disabled,true);});
check('only_same_origin_calls',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases:tests,browser_visual_acceptance:false}));
