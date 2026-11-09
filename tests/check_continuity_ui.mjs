/* Controller tests using fabricated aggregate counts, no browser or real data. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.style={};this.files=[];this.value='';this.attributes={};}
 set innerHTML(v){throw Error('Unsafe HTML');}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}setAttribute(k,v){this.attributes[k]=v;}click(){if(this.tagName==='a')downloads.push(this.download);}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};
const current={participants:100,returning:0,new:100,reference_participants:120,return_rate:0,retention_rate:0,status:'available',captured_at:'2026-10-20T00:10:00Z',reference:{start:'2026-10-06T00:00:00Z',end:'2026-10-13T00:00:00Z'}};
const fixture={project_id:1,actors:[{id:1,name:'Literal <script>x</script>',kind:'primary'}],selected_actor_id:1,accounts:[{network:'facebook',url:'https://facebook.com/fixture'}],
 selected_account:{actor_id:1,actor_name:'Literal <script>x</script>',network:'facebook',url:'https://facebook.com/fixture'},measurements:['manual:fixture-v1'],selected_measurement:'manual:fixture-v1',
 window:{start:'2026-10-13T00:00:00Z',end:'2026-10-20T00:00:00Z'},current,previous:{...current,return_rate:20},return_rate_change_pp:-20,baseline_consistent:true,
 series:[{start:'2026-10-13T00:00:00Z',end:'2026-10-20T00:00:00Z',...current}],coverage_bounded:false,can_import:true};
let project=1,response=structuredClone(fixture),deferred=null,confirmResult=false,opened=0,downloads=[],blobs=[],requests=[];
async function api(path,options={}){requests.push({path,options});assert(path.startsWith('/api/projects/'+project+'/continuity'));if(options.method==='POST')return {inserted:1,duplicates:0};if(deferred)return new Promise(r=>deferred.resolve=r);return structuredClone(response);}
const window={};vm.runInNewContext(fs.readFileSync(new URL('continuity.js',base),'utf8'),{window,document:{createElement:t=>new Element(t)},Date,Intl,Blob,URLSearchParams,setTimeout:f=>f(),confirm:()=>confirmResult,URL:{createObjectURL:b=>{blobs.push(b);return 'blob:fixture';},revokeObjectURL(){}}});
const module=window.NexoContinuity.install({api,byId,getProject:()=>project,onConfigure:()=>opened++});nodes.continuityPeriod.value='7';nodes.continuityNetwork.value='all';
const tests=[],check=(name,f)=>{f();tests.push(name);};
await module.reload();
check('source_counts_and_distinct_rates',()=>{assert.equal(nodes.continuityParticipants.textContent,'100');assert.equal(nodes.continuityReturning.textContent,'0');assert.equal(nodes.continuityRate.textContent,'0 %');assert.equal(nodes.continuityRetention.textContent,'0 %');});
check('literal_names_are_not_html',()=>assert(nodes.continuityScope.textContent.includes('<script>')));
check('only_observed_periods_rendered',()=>assert.equal(nodes.continuitySeries.children.length,1));
check('comparison_and_percentage_points',()=>{assert.equal(nodes.continuityComparison.children[0].children[1].children.length,4);assert(nodes.continuityDelta.textContent.includes('-20 puntos'));});
nodes.continuityConfigure.onclick();check('configure_opens_actors',()=>assert.equal(opened,1));
nodes.continuityExport.onclick();check('cut_export_available',()=>assert.equal(downloads.at(-1),'NEXO_Continuidad_Corte.json'));
nodes.continuityTemplate.onclick();const template=JSON.parse(await blobs.at(-1).text());
check('template_is_scoped_and_has_no_invented_counts',()=>{const t=template.items[0];assert.equal(t.actor_id,1);assert.equal(t.participants,null);assert.equal(t.reference_to,fixture.window.start);assert.equal(new Date(t.period_to)-new Date(t.period_from),new Date(t.reference_to)-new Date(t.reference_from));});
response=structuredClone(fixture);for(const key of ['participants','returning','new','reference_participants','return_rate','retention_rate'])response.current[key]=null;response.current.status='limited_sample';response.series=[];await module.reload();
check('suppressed_or_missing_metrics_never_become_zero',()=>{assert.equal(nodes.continuityParticipants.textContent,'—');assert.equal(nodes.continuityRate.textContent,'—');assert(nodes.continuitySource.textContent.includes('muestra'));});
response={...structuredClone(fixture),can_import:false};await module.reload();check('viewer_import_hidden',()=>assert.equal(nodes.continuityImportPanel.hidden,true));
response=structuredClone(fixture);await module.reload();nodes.continuityFile.files=[{size:2,text:async()=>'{}'}];nodes.continuityFile.onchange();
check('unsaved_file_prevents_project_change',()=>assert.equal(module.canLeaveProject(),false));
await nodes.continuityImportForm.onsubmit({preventDefault(){}});check('local_import_uses_current_project',()=>assert(requests.some(r=>r.options.method==='POST'&&r.path==='/api/projects/1/continuity/captures')));
let finish;nodes.continuityFile.files=[{size:2,text:()=>new Promise(r=>finish=r)}];nodes.continuityFile.onchange();const pending=nodes.continuityImportForm.onsubmit({preventDefault(){}}),before=requests.filter(r=>r.options.method==='POST').length;
project=2;module.resetProject();finish('{}');await pending;
check('late_file_read_cannot_cross_projects',()=>assert.equal(requests.filter(r=>r.options.method==='POST').length,before));
deferred={};const late=module.reload();project=3;module.resetProject();deferred.resolve(fixture);await late;
check('stale_dashboard_response_discarded',()=>assert.equal(nodes.continuityParticipants.textContent,'—'));
check('project_reset_clears_privileges_and_selections',()=>{assert.equal(nodes.continuityAccount.children.length,0);assert.equal(nodes.continuityMeasurement.children.length,0);assert.equal(nodes.continuityFile.value,'');assert(nodes.continuityImportPanel.hidden);assert(nodes.continuityExport.disabled);});
check('same_origin_requests_only',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases:tests,browser_visual_acceptance:false}));
