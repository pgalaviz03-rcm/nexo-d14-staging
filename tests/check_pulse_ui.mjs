import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const base=fileURLToPath(new URL('../static/',import.meta.url)),html=fs.readFileSync(base+'index.html','utf8');
const fixture=JSON.parse(fs.readFileSync(new URL('./fixtures/pulse-ui.json',import.meta.url),'utf8'));
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.style={};this.attributes={};this.hidden=false;this.files=[];}
 set innerHTML(value){throw Error('Unexpected untrusted HTML rendering');}
 append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}
 setAttribute(k,v){this.attributes[k]=v;}reset(){this.value='';}addEventListener(){}
}
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));const byId=id=>{assert(nodes[id],id);return nodes[id];};
const window={},document={createElement:tag=>new Element(tag),querySelectorAll:()=>[]};
for(const name of ['pulse.js','platform.js','workbench.js'])vm.runInNewContext(fs.readFileSync(base+name,'utf8'),{window,document,URLSearchParams,Date,console,confirm:()=>false});
let project=1,superadmin=true,networkRequests=0;const requests=[];
async function api(path,options={}){
 requests.push({path,options});assert(path.startsWith('/api/'));networkRequests++;
 if(path==='/api/platform/session')return {is_superadmin:superadmin};
 if(path==='/api/platform/projects')return [{id:1,name:'Proyecto de ejemplo',slug:'fixture',status:'active'}];
 if(path==='/api/platform/users')return [{id:1,email:'fixture@test.invalid',active:true}];
 if(path==='/api/branding')return {name:'NEXO',tagline:'Contexto'};
 if(path==='/api/platform/branding')return JSON.parse(options.body);
 if(path.endsWith('/pulse/config'))return fixture.config;
 if(path.includes('/pulse?')){const q=new URLSearchParams(path.split('?')[1]);const packet=structuredClone(q.get('demo')==='true'?fixture.demo:fixture.real);if(q.get('actor_id')!=='0')packet.selected_actor_id=Number(q.get('actor_id'));return packet;}
 throw Error('Unexpected route '+path);
}
const pulse=window.NexoPulse.install({api,byId,getProject:()=>project});nodes.pulseNetwork.value='all';
await pulse.reload();assert.equal(nodes.pulseMentions.textContent,'0');assert.equal(nodes.pulseScore.textContent,'—');assert(nodes.pulseSample.hidden);
assert(!html.includes('id="pulseDemo"'));fixture.config.visual_review=true;await pulse.reload();assert.equal(nodes.pulseSample.hidden,false);assert.equal(nodes.pulseMentions.textContent,'80');assert.equal(nodes.pulseActorCards.children.length,3);
const visible=n=>[n.textContent||'',...n.children.map(visible)].join(' ');
assert.equal(nodes.pulseDelta.textContent,'43.8 %');assert.equal(nodes.pulseToneBreakdown.children.length,3);
assert.equal(nodes.pulseShare.textContent,'50 %');assert.equal(nodes.pulseShareLabel.textContent,'Mayor presencia');assert.equal(nodes.pulseShareAbout.textContent,'Actor de ejemplo A');
assert(!/línea base|90 días/.test(visible(nodes.pulseActorCards)));assert(visible(nodes.pulseActorCards).includes('índice /100'));
assert(!/vistas|audiencia|alcance/i.test(visible(nodes.pulseHeadlines)));assert(visible(nodes.pulseHeadlines).includes('Publicación ficticia'));
const account=nodes.pulseAccounts.children[0];assert.equal(account.children[1].children.length,3);
assert(!/Vistas|Alcance|Impresiones|Periodo de las métricas no informado/.test(visible(account)));
assert(visible(account).includes('Seguidores')&&visible(account).includes('Publicaciones')&&visible(account).includes('Interacciones'));
const actorWithoutHistory=fixture.demo.actors[0];actorWithoutHistory.score_delta=null;fixture.demo.metrics.score_delta=null;await pulse.reload();assert(nodes.pulseToneComparison.hidden);
assert(/class="pulse-method" data-owner-only/.test(html));assert(html.includes('/assets/pulse-home.css?'));
await nodes.pulseActorFilters.children[1].onclick();await new Promise(r=>setTimeout(r,0));assert(requests.at(-1).path.includes('actor_id=1'));
fixture.config.visual_review=false;await pulse.reload();assert.equal(nodes.pulseScore.textContent,'—');assert.equal(nodes.pulseSample.hidden,true);
nodes.pulseTerritory.value='Cambios locales sin guardar';nodes.pulseConfigForm.oninput();fixture.config.version++;await pulse.reload();assert.equal(nodes.pulseTerritory.value,'Cambios locales sin guardar');assert.equal(pulse.canLeaveProject(),false);
pulse.resetProject();assert.equal(nodes.pulseActorCards.children.length,0);assert(nodes.pulseConfigForm.hidden);
let updated;const platform=window.NexoPlatform.install({api,byId,onProjectsChanged:async()=>{},onBrandChanged:b=>updated=b});
await platform.reload();assert.equal(nodes.platformNav.hidden,false);assert(!html.includes('id="platformBrandForm"'));assert(html.includes('data-settings-tab="actors"'));
superadmin=false;await platform.reload();assert.equal(nodes.platformNav.hidden,true);assert(nodes.platformForms.hidden);
const workbench=window.NexoWorkbench.install({api,byId,getProject:()=>project});await workbench.reload('actors');assert.equal(nodes.actorsContent.children.length,1);workbench.resetProject();assert.equal(nodes.actorsContent.children.length,0);
const inline=html.match(/<script>([\s\S]*?)<\/script>/)[1];const functionText=inline.slice(inline.indexOf('let requestSlots='),inline.indexOf('const htmlSafe='));
let resolve;const context=vm.createContext({authToken:null,activeProjectId:1,projectLoading:false,projectWrites:0,fetch:()=>new Promise(r=>resolve=r),Error});
vm.runInContext(functionText+';this.call=api;',context);const late=context.call('/api/projects/1/pulse');await Promise.resolve();context.activeProjectId=2;resolve({ok:true,json:async()=>({project_id:1})});await assert.rejects(late,/cambió el proyecto/);
context.projectLoading=true;await assert.rejects(context.call('/api/projects/2/pulse/import',{method:'POST'}),/termine el cambio/);assert.equal(context.projectWrites,0);
assert(networkRequests>0&&requests.every(x=>!x.path.includes('https:')));
console.log(JSON.stringify({passed:true,controller_cases:['missing_values','automatic_isolated_review','actor_filter_request','no_demo_control','project_reset','brand_editor_removed','superadmin_controls','project_settings_unsaved_guard','module_reset','stale_response_rejected','writes_during_switch_rejected','no_provider_fetch','favorable_content_percentage','actor_index_label','headlines_without_audience_claims','three_supported_account_counters','missing_history_comparison_hidden','method_owner_only','largest_share_in_overview'],browser_visual_acceptance:false}));
