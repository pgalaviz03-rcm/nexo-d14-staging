/* Canonical settings, owner isolation, secret write-only inputs and project switches. */
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.value='';this.style={};this.attributes={};this.hidden=false;this.files=[];this.disabled=false;this.checked=false;}
 append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(k,v){this.attributes[k]=v;}getAttribute(k){return this.attributes[k];}click(){}focus(){this.focused=true;}scrollIntoView(){this.scrolled=true;}
 querySelectorAll(tag){return this.children.flatMap(n=>[...(n.tagName===tag?[n]:[]),...n.querySelectorAll(tag)]);}
 set innerHTML(v){throw Error('Unsafe HTML');}
}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()]));
for(const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g))if(/\shidden(?:\s|>)/.test(match[0]))nodes[match[1]].hidden=true;
const byId=id=>{assert(nodes[id],id);return nodes[id];},text=n=>[n.textContent,...n.children.map(text)].join(' ');
let project=1,owner=true,requests=[],pending=null,opened='',reloads=0,focused=0,workbook=0;
const defaultRow={kind:'apify',name:'Apify',secret_fields:['api_token'],settings:{provider:'Apify',base_url:'https://api.apify.com',model:'',resource_ref:'',dataset_ref:'',account_ref:'',max_items:100,daily_limit:0},version:0,credentials_saved:false,state:'not_configured'};
let row=structuredClone(defaultRow),media=[],nextMediaId=3,rejectMedia=false,pendingMedia=null;
async function api(path,options={}){requests.push({path,options});assert(path.startsWith('/api/projects/'));
 if(pending)return new Promise(r=>pending.resolvers.push(()=>r(path.endsWith('/media')?{items:[]}:{items:[defaultRow]})));
 if(path.endsWith('/integrations'))return{items:[structuredClone(row)]};
 if(path.endsWith('/integrations/apify')){const b=JSON.parse(options.body);const{secrets,expected_version,clear_secrets,...settings}=b;row={...row,settings,version:expected_version+1,credentials_saved:clear_secrets?false:row.credentials_saved||Object.keys(secrets).length>0,state:'saved_locally'};return structuredClone(row);}
 if(path.endsWith('/media')||/\/media\/\d+$/.test(path)){
  if(options.method==='POST'||options.method==='PUT'){
   if(rejectMedia)throw Error('Ese nombre ya está registrado.');
   const b=JSON.parse(options.body),id=options.method==='POST'?nextMediaId++:Number(path.split('/').at(-1)),m={...b,id,version:b.expected_version+1};
   const save=()=>{media=options.method==='POST'?[...media,m]:media.map(row=>row.id===id?m:row);return structuredClone(m);};
   if(pendingMedia)return new Promise(resolve=>pendingMedia.resolve=()=>resolve(save()));
   return save();
  }return{items:structuredClone(media)};
 }
 if(path.endsWith('/publications/import'))return{inserted:1,duplicates:0};
 throw Error(path);
}
const window={},document={createElement:t=>new Element(t)};
class MockURL extends URL{static createObjectURL(){return 'blob:fixture';}static revokeObjectURL(){}}
vm.runInNewContext(fs.readFileSync(new URL('settings.js',base),'utf8'),{window,document,URL:MockURL,Date,Blob,JSON,confirm:()=>false,setTimeout:f=>f()});
const module=window.NexoSettings.install({api,byId,getProject:()=>project,getProjectName:()=>project===1?'Primero':'Segundo',canManage:()=>owner,page:p=>opened=p,onWorkbookFocus:async id=>{workbook=id;},onActorFocus:async id=>{focused=id;},onReload:async()=>{reloads++;return{items:[{id:11,name:'Actor registrado',active:true,kind:'primary'}]};}});
const cases=[],check=(name,f)=>{f();cases.push(name);};await module.reload();
check('owner_settings_scoped_to_active_project',()=>{assert(nodes.settingsProjectLabel.textContent.includes('Primero'));assert.equal(reloads,1);});
module.open('integrations');check('one_configuration_destination',()=>{assert.equal(opened,'platform');assert(!nodes.settingsPanel_integrations.hidden);assert(nodes.settingsPanel_actors.hidden);});
check('observed_actor_uses_canonical_directory',()=>{assert.equal(focused,11);assert.equal(nodes.settingsObservedActor.children.length,1);});
check('one_actor_and_rule_editor_no_old_duplicates',()=>{assert(!html.includes('id="pulseActorForm"'));assert(!html.includes('id="pulseRuleForm"'));assert(!html.includes('id="pulseAccountForm"'));assert(!html.includes('id="platformBrandForm"'));});
const input=nodes.settingsSecretFields.querySelectorAll('input')[0];input.value='not-a-live-fixture-key';nodes.settingsIntegrationForm.oninput();
check('unsaved_credential_guard',()=>assert.equal(module.canLeaveProject(),false));
await nodes.settingsIntegrationForm.onsubmit({preventDefault(){}});
check('secret_sent_only_on_owner_save_with_expected_version',()=>{const q=requests.find(r=>r.path.endsWith('/integrations/apify'));const b=JSON.parse(q.options.body);assert.equal(b.secrets.api_token,'not-a-live-fixture-key');assert.equal(b.expected_version,0);assert.equal(b.monthly_budget_usd,0);assert(!('enabled' in b));});
check('saved_secret_input_cleared_and_never_refilled',()=>{assert.equal(nodes.settingsSecretFields.querySelectorAll('input')[0].value,'');assert(nodes.settingsSecretState.textContent.includes('cifradas'));assert(!text(nodes.settingsIntegrationList).includes('fixture-key'));});
module.open('media');check('media_starts_with_one_add_action_and_closed_editor',()=>{assert(nodes.settingsMediaEditor.hidden);assert(!nodes.settingsMediaNew.hidden);assert.equal([...html.matchAll(/id="settingsMediaNew"/g)].length,1);assert.equal(nodes.settingsMediaCount.textContent,'0 registrados');});
nodes.settingsMediaNew.onclick();check('add_opens_form_and_hides_repeated_entry_action',()=>{assert(!nodes.settingsMediaEditor.hidden);assert(nodes.settingsMediaNew.hidden);assert(nodes.settingsMediaName.focused);});
nodes.settingsMediaCancel.onclick();check('cancel_clean_form_returns_to_list_without_writes',()=>{assert(nodes.settingsMediaEditor.hidden);assert(!nodes.settingsMediaNew.hidden);assert(!requests.some(r=>r.options.method==='POST'));});
nodes.settingsMediaNew.onclick();
nodes.settingsMediaName.value='Medio <script>literal</script>';nodes.settingsMediaSite.value='https://example.org';nodes.settingsMedia_facebook.value='https://facebook.com/fixture.medium';nodes.settingsMediaActive.checked=true;
await nodes.settingsMediaForm.onsubmit({preventDefault(){}});
check('outlet_social_accounts_have_canonical_owner_form',()=>{assert.equal(media.length,1);assert.equal(media[0].channels[0].network,'facebook');assert(text(nodes.settingsMediaList).includes('<script>literal</script>'));});
check('save_shows_named_confirmation_and_highlighted_saved_record',()=>{assert(nodes.settingsMediaEditor.hidden);assert(!nodes.settingsMediaNew.hidden);assert.equal(nodes.settingsMediaCount.textContent,'1 registrado');assert.equal(nodes.settingsMediaStatus.getAttribute('data-state'),'success');assert(nodes.settingsMediaStatus.textContent.includes(media[0].name));assert.equal(nodes.settingsMediaList.children[0].getAttribute('data-saved'),'true');assert(nodes.settingsMediaList.focused&&nodes.settingsMediaList.scrolled);});
check('saved_record_exposes_site_and_registered_social_links',()=>{const links=nodes.settingsMediaList.querySelectorAll('a');assert.equal(links.length,2);assert.equal(links[0].href,'https://example.org');assert.equal(links[1].href,'https://facebook.com/fixture.medium');assert(links.every(a=>a.rel==='noopener noreferrer'));});
await module.reload();check('saved_medium_remains_visible_after_reload',()=>{assert(text(nodes.settingsMediaList).includes(media[0].name));assert.equal(nodes.settingsMediaList.children.length,1);});
nodes.settingsMediaList.children[0].children.at(-1).onclick();check('edit_opens_existing_values_with_distinct_save_label',()=>{assert(!nodes.settingsMediaEditor.hidden);assert(nodes.settingsMediaNew.hidden);assert.equal(nodes.settingsMediaName.value,media[0].name);assert.equal(nodes.settingsMediaSave.textContent,'Guardar cambios');});
nodes.settingsMediaName.value='Medio actualizado';nodes.settingsMediaForm.oninput();rejectMedia=true;await nodes.settingsMediaForm.onsubmit({preventDefault(){}});
check('failed_save_retains_input_and_displays_error_without_success',()=>{assert(!nodes.settingsMediaEditor.hidden);assert.equal(nodes.settingsMediaName.value,'Medio actualizado');assert.equal(nodes.settingsMediaStatus.getAttribute('data-state'),'error');assert(nodes.settingsMediaStatus.textContent.includes('No se pudo guardar'));assert(!nodes.settingsMediaSave.disabled);assert.equal(module.canLeaveProject(),false);});
nodes.settingsMediaCancel.onclick();check('cancel_preserves_dirty_form_when_discard_is_declined',()=>{assert(!nodes.settingsMediaEditor.hidden);assert.equal(nodes.settingsMediaName.value,'Medio actualizado');});
rejectMedia=false;pendingMedia={};const saving=nodes.settingsMediaForm.onsubmit({preventDefault(){}}),beforeDuplicate=requests.length;await nodes.settingsMediaForm.onsubmit({preventDefault(){}});
check('saving_has_feedback_and_prevents_duplicate_submission',()=>{assert.equal(requests.length,beforeDuplicate);assert(nodes.settingsMediaSave.disabled);assert(nodes.settingsMediaCancel.disabled);assert.equal(nodes.settingsMediaStatus.getAttribute('data-state'),'pending');});
pendingMedia.resolve();await saving;pendingMedia=null;
check('edit_updates_same_medium_without_duplicate_and_confirms_name',()=>{assert.equal(media.length,1);assert.equal(media[0].version,2);assert.equal(media[0].name,'Medio actualizado');assert(nodes.settingsMediaEditor.hidden);assert(nodes.settingsMediaStatus.textContent.includes('Medio actualizado se actualizó'));const q=requests.filter(r=>r.path.endsWith('/media/3')).at(-1);assert.equal(q.options.method,'PUT');assert.equal(JSON.parse(q.options.body).expected_version,1);});
nodes.settingsMediaNew.onclick();nodes.settingsMediaName.value='Segundo medio';nodes.settingsMediaSite.value='https://example.net';await nodes.settingsMediaForm.onsubmit({preventDefault(){}});
check('new_medium_is_shown_first_with_updated_count',()=>{assert.equal(nodes.settingsMediaCount.textContent,'2 registrados');assert(text(nodes.settingsMediaList.children[0]).includes('Segundo medio'));assert.equal(nodes.settingsMediaList.children[0].getAttribute('data-saved'),'true');});
check('rss_registration_is_clearly_distinct_from_media_save',()=>{assert(html.includes('Registrar RSS'));assert(!html.includes('>+ Registrar</button>'));});
const source=nodes.settingsMediaImportSource;source.value='3';source.onchange();nodes.settingsMediaImportAccount.value='https://facebook.com/fixture.medium';
nodes.settingsMediaImportFile.files=[{size:100,text:async()=>JSON.stringify({captured_at:'2026-10-27T10:00:00Z',items:[]})}];await nodes.settingsMediaImportForm.onsubmit({preventDefault(){}});
check('outlet_ingress_targets_selected_project_and_medium',()=>{const q=requests.find(r=>r.path.includes('/publications/import'));assert.equal(q.path,'/api/projects/1/settings/media/3/publications/import');assert.equal(JSON.parse(q.options.body).account_url,media[0].channels[0].url);});
module.resetProject();check('reset_clears_credentials_media_and_private_values',()=>{assert.equal(nodes.settingsSecretFields.children.length,0);assert.equal(nodes.settingsProvider.value,'');assert.equal(nodes.settingsMediaName.value,'');assert.equal(nodes.settingsMediaList.children.length,0);assert(nodes.settingsMediaEditor.hidden);assert(!nodes.settingsMediaNew.hidden);assert.equal(nodes.settingsMediaStatus.textContent,'');assert.equal(nodes.settingsMediaCount.textContent,'0 registrados');});
owner=false;const before=requests.length;await module.reload();module.open('actors');await nodes.settingsMediaForm.onsubmit({preventDefault(){}});await nodes.settingsIntegrationForm.onsubmit({preventDefault(){}});
check('reader_cannot_load_or_write_configuration',()=>assert.equal(requests.length,before));
owner=true;project=1;pending={resolvers:[]};const late=module.reload();project=2;module.resetProject();pending.resolvers.forEach(r=>r());await late;pending=null;
check('late_configuration_cannot_cross_projects',()=>{assert.equal(nodes.settingsIntegrationList.children.length,0);assert.equal(nodes.settingsMediaList.children.length,0);assert.equal(nodes.settingsSecretFields.children.length,0);});
await module.reload();check('empty_new_project_can_be_configured',()=>assert(nodes.settingsProjectLabel.textContent.includes('Segundo')));
module.open('actors');nodes.settingsTab_actors.onkeydown({key:'ArrowRight',preventDefault(){}});check('keyboard_navigation_between_settings_tabs',()=>assert(!nodes.settingsPanel_team.hidden));
module.focusWorkbook(9);await module.reload();check('workbook_configuration_opens_correct_document',()=>{assert.equal(workbook,9);assert(!nodes.settingsPanel_data.hidden);});
check('no_provider_or_outbound_requests',()=>assert(requests.every(r=>r.path.startsWith('/api/projects/'))));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
