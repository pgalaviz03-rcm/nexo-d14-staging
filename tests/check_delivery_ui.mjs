import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{constructor(){this.children=[];this.value='';this.style={};this.listeners={};this.checked=false;}set innerHTML(v){throw Error('Untrusted HTML rendering');}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}addEventListener(k,f){this.listeners[k]=f;}reset(){}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()])),byId=id=>{assert(nodes[id],id);return nodes[id];};
let cut=JSON.parse(fs.readFileSync(new URL('fixtures/briefing-ui.json',import.meta.url),'utf8'));let project=1,received,deferred=null,analysisDeferred=null;const requests=[];
let settings={version:0,channel:'email',frequency:'daily',local_time:'07:00',timezone:'America/Mexico_City',weekday:0,lookback_days:1,enabled:false,destination_masked:null};
async function api(path,options={}){
 requests.push({path,method:options.method||'GET',body:options.body});
 assert(path.startsWith('/api/projects/'+project+'/briefing/'));
 if(path.endsWith('/analysis/prepare'))return {queued:3,external_calls:0};
 if(path.includes('/analysis?')){if(analysisDeferred)return new Promise(r=>analysisDeferred.resolve=r);return {counts:{queued:3,completed:0,processing:0,needs_review:0,failed:0,unqueued:0}};}
 if(path.endsWith('/preview')){if(deferred)return new Promise(r=>deferred.resolve=r);return {text:'Vista literal <script>sin ejecutar</script>',actual_delivery_enabled:false};}
 if(path.endsWith('/simulate'))return {id:1,state:'blocked_provider',is_simulation:true};
 if(path.includes('/assessments?'))return {items:[],truncated:false};
 if(options.method==='PUT'){received=JSON.parse(options.body);settings={...settings,...received,version:1,destination_masked:'f***@test.invalid'};return settings;}
 return {settings,jobs:[]};
}
const window={};vm.runInNewContext(fs.readFileSync(new URL('delivery.js',base),'utf8'),{window,document:{createElement:()=>new Element()},Intl,Date,URLSearchParams,confirm:()=>false});
const module=window.NexoDelivery.install({api,byId,getProject:()=>project,getCut:()=>cut,onAssessmentSaved:async()=>{}});
await module.reload();assert.equal(nodes.deliveryChannel.value,'email');assert.equal(nodes.deliverySimulate.disabled,true);
nodes.deliveryDestination.value='fixture@test.invalid';nodes.deliveryConsent.checked=true;nodes.deliveryEnabled.checked=true;nodes.deliveryForm.listeners.input();assert.equal(module.canLeaveProject(),false);
await nodes.deliveryForm.onsubmit({preventDefault(){}});assert.equal(received.expected_version,0);assert(!('user_id' in received));assert.equal(nodes.deliveryDestination.value,'');assert(nodes.deliveryDestination.placeholder.includes('f***'));assert.equal(nodes.deliverySimulate.disabled,false);
await nodes.deliveryPreview.onclick();assert.equal(nodes.deliveryPreviewText.textContent,'Vista literal <script>sin ejecutar</script>');
await nodes.deliverySimulate.onclick();assert(nodes.deliveryStatus.textContent.includes('Ningún mensaje enviado'));
cut.can_save=false;module.cutChanged(cut);assert.equal(nodes.assessmentPanel.hidden,true);cut.can_save=true;module.cutChanged(cut);assert.equal(nodes.assessmentPanel.hidden,false);
deferred={};const pending=nodes.deliveryPreview.onclick();module.cutChanged(cut);deferred.resolve({text:'old cut'});await pending;assert.equal(nodes.deliveryPreviewText.textContent,'');
project=2;module.resetProject();assert(!nodes.deliveryDestination.placeholder.includes('f***'));assert.equal(nodes.deliveryJobs.children.length,0);assert.equal(nodes.deliverySimulate.disabled,true);
deferred=null;cut.can_save=true;module.cutChanged(cut);await new Promise(setImmediate);
assert(nodes.briefingAnalysisState.textContent.includes('3 pendientes de análisis'));
assert(requests.some(r=>r.path.endsWith('/analysis/prepare')&&r.method==='POST'));
const prepared=requests.filter(r=>r.path.endsWith('/analysis/prepare')).length;
cut.can_save=false;module.cutChanged(cut);await new Promise(setImmediate);
assert.equal(requests.filter(r=>r.path.endsWith('/analysis/prepare')).length,prepared);
const readerRequestCount=requests.length;module.cutChanged(cut);await new Promise(setImmediate);assert.equal(requests.length,readerRequestCount);
analysisDeferred={};cut.can_save=true;module.cutChanged(cut);await new Promise(setImmediate);const old=analysisDeferred.resolve;
module.cutChanged(null);old({counts:{completed:999,queued:0,processing:0,needs_review:0,failed:0}});await new Promise(setImmediate);
assert.equal(nodes.briefingAnalysisState.textContent,'');
assert(!html.includes('value="whatsapp"')&&!html.includes('whatsappbusiness.com'));
assert(html.includes('Revisar resultados y corregir una pieza'));
console.log(JSON.stringify({passed:true,cases:['private_schedule_form','masked_target','no_user_id_injection','no_provider_fetch','literal_preview','simulation_not_sent','viewer_review_controls','stale_cut_discarded','project_private_fields_cleared','automatic_analysis_queue','pending_analysis_state','reader_never_queues','late_analysis_discarded','unsupported_channel_absent','optional_correction'],browser_visual_acceptance:false}));
