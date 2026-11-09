import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const base=new URL('../static/',import.meta.url),html=fs.readFileSync(new URL('index.html',base),'utf8');
class Element{constructor(){this.children=[];this.value='';this.textContent='';this.hidden=false;this.attributes={};this.style={};}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}setAttribute(k,v){this.attributes[k]=v;}reset(){}}
const nodes=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>[x[1],new Element()]));const byId=id=>{assert(nodes[id],id);return nodes[id];};
let cloud=true,owner=true,requests=[];
async function api(path,options={}){requests.push({path,options});if(path.endsWith('/session'))return{is_superadmin:owner,auth_mode:cloud?'supabase':'local'};if(path.endsWith('/projects'))return[{id:1,name:'Synthetic',slug:'synthetic',status:'active'}];if(path.endsWith('/users'))return options.method?{id:4}:[{id:1,email:'synthetic@example.invalid',active:true}];throw Error(path);}
const window={},document={createElement:()=>new Element(),documentElement:new Element()};vm.runInNewContext(fs.readFileSync(new URL('platform.js',base),'utf8'),{window,document});
const app=window.NexoPlatform.install({api,byId,onProjectsChanged:async()=>{}}),cases=[];function check(n,f){f();cases.push(n);}
nodes.platformUserPassword.value='must-be-cleared';await app.reload();
check('cloud_account_form_never_requests_local_password',()=>{assert(nodes.platformUserPassword.hidden);assert(!nodes.platformUserPassword.required);assert.equal(nodes.platformUserPassword.value,'');assert(!nodes.platformUserSubject.hidden);assert(nodes.platformUserSubject.required);assert.equal(nodes.platformUserSave.textContent,'Vincular cuenta');});
nodes.platformUserEmail.value='new@example.invalid';nodes.platformUserSubject.value='11111111-1111-4111-8111-111111111111';await nodes.platformUserForm.onsubmit({preventDefault(){}});
check('cloud_submit_links_subject_without_password',()=>{const body=JSON.parse(requests.find(r=>r.options.method==='POST').options.body);assert.equal(body.auth_subject,'11111111-1111-4111-8111-111111111111');assert(!('password' in body));});
cloud=false;await app.reload();check('local_account_form_keeps_password_flow',()=>{assert(!nodes.platformUserPassword.hidden);assert(nodes.platformUserPassword.required);assert(nodes.platformUserSubject.hidden);assert(!nodes.platformUserSubject.required);});
owner=false;await app.reload();check('reader_has_no_platform_configuration',()=>assert(nodes.platformForms.hidden&&nodes.platformNav.hidden));
check('all_requests_use_same_origin',()=>assert(requests.every(r=>r.path.startsWith('/api/platform/'))));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
