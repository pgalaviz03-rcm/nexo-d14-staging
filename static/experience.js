/* Accessible drawer + progressive select enhancement. No data or role storage. */
window.NexoExperience={install(){
 const emotionDetails=document.getElementById('pulseEmotionDetails');if(emotionDetails&&innerWidth<=640)emotionDetails.open=false;
 const app=document.querySelector('.app'),menu=document.getElementById('openNavigation'),shade=document.getElementById('navigationShade');
 const close=()=>{app.dataset.menuOpen='false';menu.setAttribute('aria-expanded','false');};
 const open=()=>{app.dataset.menuOpen='true';menu.setAttribute('aria-expanded','true');document.querySelector('.sidebar .nav-btn.active')?.focus();};
 menu.onclick=()=>app.dataset.menuOpen==='true'?close():open();shade.onclick=()=>{close();menu.focus();};
 document.querySelectorAll('[data-page]').forEach(n=>n.addEventListener('click',close));
 document.getElementById('moreNavigation').onclick=open;
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&app.dataset.menuOpen==='true'){close();menu.focus();}});
 document.querySelector('.sidebar').addEventListener('keydown',e=>{
  if(e.key!=='Tab'||app.dataset.menuOpen!=='true')return;
  const list=[...document.querySelector('.sidebar').querySelectorAll('button:not([disabled]),summary,[tabindex="0"]')].filter(n=>n.offsetParent!==null);
  const first=list[0],last=list.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
 });
 const records=new Set();let active=null,sequence=0;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 function dismiss(focus=false){if(!active)return;const record=active;active=null;record.button.setAttribute('aria-expanded','false');record.pop.remove();if(focus)record.button.focus();}
 function sync(record){const select=record.select;if(!select.isConnected){if(active===record)dismiss();records.delete(record);return;}
  const selected=select.selectedOptions[0];record.title.textContent=selected?.textContent||'Seleccionar';record.button.disabled=select.matches(':disabled');
  record.button.setAttribute('aria-label',record.label+': '+record.title.textContent);
  if(active===record&&record.button.disabled)dismiss();
 }
 function position(r){const b=r.button.getBoundingClientRect();r.pop.style.width=Math.max(190,b.width)+'px';
  if(innerWidth>640){const h=Math.min(360,r.pop.scrollHeight),top=b.bottom+6+h<innerHeight?b.bottom+6:Math.max(8,b.top-h-6);
   r.pop.style.top=top+'px';r.pop.style.left=Math.max(12,Math.min(b.left,innerWidth-Math.max(190,b.width)-12))+'px';}
 }
 function show(r){if(r.button.disabled)return;if(active===r){dismiss();return;}dismiss();active=r;
  const pop=el('div',undefined,'nexo-select-popover');pop.id='nexo-options-'+r.id;r.pop=pop;
  const head=el('div',undefined,'nexo-select-heading'),exit=el('button','×');exit.type='button';exit.setAttribute('aria-label','Cerrar opciones');exit.onclick=()=>dismiss(true);head.append(el('span',r.label),exit);pop.append(head);
  const list=el('div',undefined,'nexo-select-options');list.id='nexo-list-'+r.id;list.setAttribute('role','listbox');list.setAttribute('aria-label',r.label);
  let search=null;const options=[...r.select.options];
  function choose(option){r.select.value=option.value;r.select.dispatchEvent(new Event('change',{bubbles:true}));sync(r);dismiss(true);}
  function draw(query=''){list.replaceChildren();for(const option of options){if(option.disabled||option.hidden||query&&!option.textContent.toLocaleLowerCase().includes(query.toLocaleLowerCase()))continue;
    const button=el('button',undefined,'nexo-select-option');button.type='button';button.setAttribute('role','option');button.setAttribute('aria-selected',String(option.selected));button.append(el('span',option.textContent),el('span',option.selected?'✓':''));
    button.onclick=()=>choose(option);button.onkeydown=e=>{if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const rows=[...list.querySelectorAll('button')],i=rows.indexOf(button);rows[e.key==='Home'?0:e.key==='End'?rows.length-1:(i+(e.key==='ArrowDown'?1:-1)+rows.length)%rows.length]?.focus();}};list.append(button);
   }if(!list.children.length)list.append(el('p','No hay coincidencias.','nexo-select-empty'));
  }
  if(options.length>8){search=el('input',undefined,'nexo-select-search');search.type='search';search.placeholder='Buscar opción…';search.setAttribute('aria-label','Buscar en '+r.label);search.oninput=()=>{draw(search.value);position(r);};search.onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();list.querySelector('button')?.focus();}};pop.append(search);}
  draw();pop.append(list);document.body.append(pop);r.button.setAttribute('aria-expanded','true');position(r);
  pop.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();dismiss(true);}if(e.key==='Tab'){e.preventDefault();dismiss(true);}});
  (search||list.querySelector('[aria-selected=true]')||list.querySelector('button')||exit).focus();
 }
 function enhance(select){if(select.dataset.nexoSelect||select.multiple||select.size>1)return;select.dataset.nexoSelect='true';
  const labelNode=select.labels?.[0]?.cloneNode(true);labelNode?.querySelectorAll('select').forEach(n=>n.remove());
  const label=labelNode?.textContent.replace(/\s+/g,' ').trim().slice(0,75)||select.getAttribute('aria-label')||'Seleccionar';
  const id=++sequence,wrapper=el('span',undefined,'nexo-select'),button=el('button',undefined,'nexo-select-trigger'),title=el('span');button.type='button';button.append(title,el('span','⌄'));button.setAttribute('role','combobox');button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','nexo-list-'+id);
  select.before(wrapper);wrapper.append(select,button);select.classList.add('nexo-select-source');select.tabIndex=-1;select.setAttribute('aria-hidden','true');
  const record={select,wrapper,button,title,label,id};records.add(record);button.onclick=()=>show(record);
  button.onkeydown=e=>{if(['ArrowDown','ArrowUp','Enter',' '].includes(e.key)){e.preventDefault();show(record);}};
  select.addEventListener('change',()=>{button.removeAttribute('aria-invalid');sync(record);});select.addEventListener('invalid',e=>{e.preventDefault();button.setAttribute('aria-invalid','true');button.focus();show(record);});select.addEventListener('focus',()=>button.focus());
  new MutationObserver(()=>sync(record)).observe(select,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','selected','label','hidden']});sync(record);
 }
 const discover=()=>{document.querySelectorAll('select:not([data-nexo-select])').forEach(enhance);for(const r of records)sync(r);};
 let scheduled=false;new MutationObserver(changes=>{
  if(changes.every(c=>c.target.closest?.('.nexo-select-popover,.nexo-select-trigger')))return;
  if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;discover();});
 }).observe(document.querySelector('.app'),{childList:true,subtree:true});
 document.addEventListener('reset',()=>requestAnimationFrame(discover));document.addEventListener('pointerdown',e=>{if(active&&!active.pop.contains(e.target)&&!active.wrapper.contains(e.target))dismiss();});
 addEventListener('resize',()=>{if(innerWidth>900)close();if(active)position(active);});
 addEventListener('scroll',()=>{if(active&&innerWidth>640)position(active);},true);
 discover();return{closeNavigation:close,refresh:discover};
}};
document.addEventListener('DOMContentLoaded',()=>window.NexoExperience.install());
