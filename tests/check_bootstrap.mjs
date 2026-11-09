import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import crypto from 'node:crypto';
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8'),bundle=fs.readFileSync(new URL('../static/nexo-modules.js',import.meta.url),'utf8');
const scripts=[...html.matchAll(/<script(?: src="([^"]+)")?>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,2);assert(scripts[0][1].endsWith(crypto.createHash('sha256').update(bundle).digest('hex').slice(0,16)));assert(!scripts[1][1]);
class Element{
 constructor(id=''){this.id=id;this.children=[];this.dataset={};this.style={};this.attributes={};this.listeners={};this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.files=[];this.classList={add(){},remove(){},toggle(){},contains(){return false;}};}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}addEventListener(k,fn){this.listeners[k]=fn;}setAttribute(k,v){this.attributes[k]=v;}removeAttribute(k){delete this.attributes[k];}querySelector(){return new Element();}querySelectorAll(){return [];}reset(){}focus(){}scrollIntoView(){}getAttribute(k){return this.attributes[k]??null;}
}
const ids=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>[m[1],new Element(m[1])])),events={},calls=[];
const document={getElementById(id){assert(ids[id],'Missing actual HTML element: '+id);return ids[id];},createElement:()=>new Element(),querySelectorAll:()=>[],querySelector:()=>null,addEventListener:(k,f)=>events[k]=f,documentElement:new Element()};
const fetch=async(path)=>{calls.push(path);return{ok:path==='/api/branding',status:path==='/api/branding'?200:401,json:async()=>path==='/api/branding'?{name:'NEXO',tagline:'Contexto'}:{detail:'No autenticado'}};};
const ctx={window:{},document,fetch,console,location:{hash:'',search:'',pathname:'/'},history:{replaceState(){}},URL,URLSearchParams,FormData,Blob,Number,String,Date,JSON,Intl,setTimeout,clearTimeout,confirm:()=>false};vm.createContext(ctx);
vm.runInContext(bundle,ctx,{filename:'nexo-modules.js'});
for(const name of [...scripts[1][2].matchAll(/window\.(Nexo\w+)\.install/g)].map(m=>m[1]))assert.equal(typeof ctx.window[name]?.install,'function',name);
vm.runInContext(scripts[1][2].replace('})();','window.__testApi=api;})();'),ctx,{filename:'bootstrap.js'});await new Promise(r=>setTimeout(r,0));
assert.equal(ids.loginError.textContent,'');assert(calls.includes('/api/projects'));assert(calls.includes('/api/branding'));assert.equal(typeof ids.mfaForm.listeners.submit,'function');assert.equal(typeof ids.loginForm.listeners.submit,'function');
let active=0,maxActive=0;ctx.fetch=async()=>{active++;maxActive=Math.max(active,maxActive);await new Promise(r=>setTimeout(r,5));return{ok:true,status:200,json:async()=>{await new Promise(r=>setTimeout(r,2));active--;return{};}};};
await Promise.all(Array.from({length:16},(_,i)=>ctx.window.__testApi('/test/'+i)));assert.equal(maxActive,2);assert.equal(active,0);
console.log(JSON.stringify({passed:true,cases:['single_versioned_asset','bundle_hash_matches_HTML','all_install_contracts_present','full_bootstrap_reaches_session_restore','login_and_mfa_handlers_installed','unauthenticated_boot_has_no_JS_error','API_fanout_bounded_to_two_until_body_consumed'],browser_rendering:false}));
