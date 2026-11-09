import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const events={},globalEvents={},cases=[];let document;
class Node{
 constructor(tag='div',text=''){this.tagName=tag;this.textContent=text;this.children=[];this.parentNode=null;this.dataset={};this.style={};this.attributes={};this.listeners={};this.disabled=false;this.hidden=false;this._value='';this.className='';this.size=0;this.multiple=false;this.labels=[];
  this.classList={add:n=>{this.className+=' '+n;},contains:n=>this.className.split(' ').includes(n)};
 }
 append(...nodes){for(const n of nodes){n.remove();n.parentNode=this;this.children.push(n);}}
 before(n){const p=this.parentNode;n.remove();n.parentNode=p;p.children.splice(p.children.indexOf(this),0,n);}
 remove(){if(this.parentNode){const p=this.parentNode;p.children=p.children.filter(n=>n!==this);this.parentNode=null;}}
 replaceChildren(...nodes){for(const c of [...this.children])c.remove();this.append(...nodes);}
 setAttribute(k,v){this.attributes[k]=String(v);}getAttribute(k){return this.attributes[k]??null;}removeAttribute(k){delete this.attributes[k];}
 addEventListener(k,f){(this.listeners[k]??=[]).push(f);}dispatchEvent(e){this['on'+e.type]?.(e);for(const f of this.listeners[e.type]||[])f(e);}
 get options(){return this.children.filter(n=>n.tagName==='option');}get selectedOptions(){return this.options.filter(n=>n.value===this.value);}get selected(){return this.parentNode?.value===this.value;}
 get value(){return this._value;}set value(v){this._value=String(v);}get isConnected(){return this===document.body||!!this.parentNode?.isConnected;}
 get offsetParent(){return this.hidden?null:this.parentNode;}get scrollHeight(){return 240;}
 getBoundingClientRect(){return{left:100,top:100,bottom:140,width:180};}focus(){document.activeElement=this;}
 matches(s){if(s===':disabled')return this.disabled;if(s==='button')return this.tagName==='button';return false;}
 contains(n){return this===n||this.children.some(c=>c.contains(n));}cloneNode(){return new Node(this.tagName,this.textContent);}
 closest(){return null;}
 querySelectorAll(selector){let all=this.children.flatMap(c=>[c,...c.querySelectorAll('*')]);if(selector==='*')return all;
  if(selector==='button')return all.filter(n=>n.tagName==='button');if(selector==='select')return all.filter(n=>n.tagName==='select');
  if(selector==='[aria-selected=true]')return all.filter(n=>n.attributes['aria-selected']==='true');return [];
 }querySelector(s){return this.querySelectorAll(s)[0]||null;}
 set innerHTML(v){throw Error('Untrusted markup');}
}
const body=new Node('body'),app=new Node(),sidebar=new Node(),menu=new Node('button'),shade=new Node('button'),more=new Node('button'),nav=new Node('button'),label=new Node('label','Canal'),select=new Node('select');
select.id='channel';select.labels=[label];for(const [value,text] of [['all','Todos'],['press','Prensa'],['facebook','Facebook']]){const o=new Node('option',text);o.value=value;select.append(o);}select.value='all';label.append(select);app.append(sidebar,menu,shade,more,label,nav);body.append(app);
const ids={openNavigation:menu,navigationShade:shade,moreNavigation:more};
document={body,activeElement:null,createElement:t=>new Node(t),getElementById:id=>ids[id],addEventListener:(k,f)=>{(events[k]??=[]).push(f);},
 querySelector:s=>s==='.app'?app:s==='.sidebar'?sidebar:nav,
 querySelectorAll:s=>s==='[data-page]'?[nav]:s==='select:not([data-nexo-select])'&&!select.dataset.nexoSelect?[select]:[]};
class Observer{observe(){}}
class Event{constructor(type){this.type=type;}}
const context={window:{},document,MutationObserver:Observer,Event,innerWidth:1100,innerHeight:800,
 requestAnimationFrame:f=>f(),addEventListener:(k,f)=>globalEvents[k]=f,console};vm.createContext(context);
vm.runInContext(fs.readFileSync(new URL('../static/experience.js',import.meta.url),'utf8'),context);
const module=context.window.NexoExperience.install(),check=(name,fn)=>{fn();cases.push(name);};
const trigger=select.parentNode.children.find(n=>n.tagName==='button');
check('native_select_retained_for_forms',()=>{assert(select.classList.contains('nexo-select-source'));assert.equal(select.value,'all');});
check('label_excludes_native_option_list',()=>assert.equal(trigger.attributes['aria-label'],'Canal: Todos'));
check('combobox_is_keyboard_focusable_and_closed',()=>{assert.equal(trigger.attributes.role,'combobox');assert.equal(trigger.attributes['aria-expanded'],'false');});
menu.onclick();check('mobile_drawer_opens',()=>assert.equal(app.dataset.menuOpen,'true'));
shade.onclick();check('drawer_shade_closes_and_restores_focus',()=>{assert.equal(app.dataset.menuOpen,'false');assert.equal(document.activeElement,menu);});
trigger.onclick();let pop=body.children.find(n=>n.className==='nexo-select-popover'),list=pop.children.find(n=>n.className==='nexo-select-options');
check('custom_listbox_opens',()=>{assert.equal(trigger.attributes['aria-expanded'],'true');assert.equal(list.attributes.role,'listbox');});
let changed=0;select.onchange=()=>changed++;list.children[1].onclick();
check('custom_choice_updates_native_selection_and_change_handler',()=>{assert.equal(select.value,'press');assert.equal(changed,1);assert.equal(trigger.children[0].textContent,'Prensa');});
check('choice_closes_popup_and_restores_focus',()=>{assert.equal(trigger.attributes['aria-expanded'],'false');assert.equal(document.activeElement,trigger);});
trigger.onkeydown({key:'ArrowDown',preventDefault(){}});pop=body.children.find(n=>n.className==='nexo-select-popover');
for(const f of pop.listeners.keydown)f({key:'Escape',preventDefault(){},stopPropagation(){}});
check('escape_closes_listbox',()=>assert.equal(trigger.attributes['aria-expanded'],'false'));
select.disabled=true;module.refresh();check('disabled_state_is_respected',()=>assert(trigger.disabled));select.disabled=false;module.refresh();
for(let i=0;i<9;i++){const o=new Node('option','Zona '+i);o.value='zone'+i;select.append(o);}trigger.onclick();pop=body.children.find(n=>n.className==='nexo-select-popover');
const search=pop.children.find(n=>n.tagName==='input');search.value='Zona 7';search.oninput();list=pop.children.find(n=>n.className==='nexo-select-options');
check('long_lists_can_be_searched',()=>assert.equal(list.children.length,1));list.children[0].onclick();
check('search_result_preserves_underlying_value',()=>assert.equal(select.value,'zone7'));
const html=fs.readFileSync(new URL('../static/index.html',import.meta.url),'utf8'),css=fs.readFileSync(new URL('../static/experience.css',import.meta.url),'utf8');
check('simplified_and_demo_controls_removed',()=>{assert(!html.includes('toggleClientMode'));assert(!html.includes('id="pulseDemo"'));});
check('other_channel_removed_from_pulse_filter',()=>{const filter=html.match(/id="pulseNetwork"[\s\S]*?<\/select>/)[0];assert(!filter.includes('value="other"'));});
check('mobile_layout_breakpoints_and_bottom_navigation_present',()=>{assert(css.includes('@media(max-width:640px)'));assert(css.includes('@media(max-width:900px)'));assert(html.includes('module-mobile-nav'));});
check('reader_administration_hidden_independently_of_module_updates',()=>assert(css.includes('html[data-nexo-access=reader] [data-owner-only]')));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false,layout_visual_qa:false}));
