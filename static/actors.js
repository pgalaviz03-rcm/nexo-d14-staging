/* Public dossiers share Pulse actor IDs. No external fetch or credential storage. */
window.NexoActors={install({api,byId,getProject,onChanged,onOpenPulse}){
 let data=null,sequence=0,selected=null,dirty=false,saving=false;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const base=()=>'/api/projects/'+getProject()+'/actors';
 const send=(suffix,body,method='POST')=>api(base()+suffix,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const message=t=>{byId('actorsStatus').textContent=t;byId('settingsActorsStatus').textContent=t;};
 const networks={facebook:'Facebook',instagram:'Instagram',x:'X',tiktok:'TikTok',youtube:'YouTube',press:'Prensa',other:'Sitio público'};
 function discard(){return !dirty||confirm('Hay una ficha sin guardar. ¿Descartar sus cambios?');}
 function clearEditor(){selected=null;dirty=false;byId('actorForm').reset();for(const id of ['actorName','actorRole','actorOrganization','actorTerritory','actorDescription','actorAliases'])byId(id).value='';byId('actorChannels').replaceChildren();byId('actorEditor').hidden=true;byId('actorFormMessage').textContent='';}
 function addChannel(value={}){const row=el('div',undefined,'actor-channel-editor');
  const field=(label,input)=>{const box=el('label',label);box.append(input);row.append(box);return input;};
  const network=el('select');for(const [key,label] of Object.entries(networks)){const o=el('option',label);o.value=key;network.append(o);}network.value=value.network||'facebook';field('Red',network);
  const url=el('input');url.type='url';url.required=true;url.maxLength=1500;url.value=value.url||'';url.placeholder='https://…';field('Perfil público',url);
  const external=el('input');external.maxLength=160;external.value=value.external_id||'';field('Identificador del proveedor, opcional',external);
  const enabled=el('input');enabled.type='checkbox';enabled.checked=value.enabled!==false;field('Incluir en seguimiento',enabled);
  const reviewed=el('input');reviewed.type='checkbox';reviewed.checked=value.review==='reviewed';field('Revisé que el enlace corresponde al actor',reviewed);
  const remove=el('button','Quitar referencia','outline');remove.type='button';remove.onclick=()=>{row.remove();dirty=true;};row.append(remove);
  row.read=()=>({network:network.value,url:url.value.trim(),external_id:external.value.trim(),enabled:enabled.checked,review:reviewed.checked?'reviewed':'unreviewed'});
  byId('actorChannels').append(row);
 }
 function openEditor(row=null){if(saving||!data?.can_manage||!discard())return;clearEditor();selected=row;
  byId('actorEditor').hidden=false;byId('actorEditorTitle').textContent=row?'Editar ficha pública':'Añadir actor público';
  for(const [id,key] of [['actorName','name'],['actorRole','public_role'],['actorOrganization','organization'],['actorTerritory','territory'],['actorDescription','description']])byId(id).value=row?.[key]||'';
  byId('actorAliases').value=(row?.aliases||[]).join('\n');byId('actorKindLabel').hidden=!!row;
  byId('actorKind').value=data.items.some(x=>x.active&&x.kind==='primary')?'comparator':'primary';
  for(const c of row?.channels||[])addChannel(c);byId('actorName').focus();
 }
 function showDetail(row){if(saving||!discard())return;clearEditor();const root=byId('actorDetail');root.replaceChildren();root.hidden=false;
  root.append(el('div',row.kind==='primary'?'ACTOR PRINCIPAL':'ACTOR COMPARATIVO','eyebrow'),el('h3',row.name),el('p',[row.public_role,row.organization,row.territory].filter(Boolean).join(' · ')||'Ficha pública del proyecto','note'));
  if(row.description)root.append(el('p',row.description,'actor-description'));
  if(row.aliases.length)root.append(el('p','También aparece como: '+row.aliases.join(' · '),'note'));
  root.append(el('h4','Cuentas y referencias públicas'));
  for(const c of row.channels){const line=el('div',undefined,'actor-reference'),a=el('a',networks[c.network]||c.network);a.href=c.url;a.target='_blank';a.rel='noopener noreferrer';
   line.append(a,el('small',(c.enabled&&row.active?'En seguimiento':'Pausada')+' · '+(c.review==='reviewed'?'Referencia revisada':'Por revisar')));root.append(line);}
  if(!row.channels.length)root.append(el('p','Añade los perfiles públicos que se observarán para este actor.','note'));
  root.append(el('p',row.mentions_in_archive.toLocaleString('es-MX')+' menciones en archivo · '+row.account_snapshots.toLocaleString('es-MX')+' capturas de cuentas','note'));
  const actions=el('div',undefined,'actions');if(row.active){const pulse=el('button','Ver en Pulso','outline');pulse.type='button';pulse.onclick=()=>onOpenPulse(row.id);actions.append(pulse);}

  root.append(actions);root.scrollIntoView?.({block:'nearest',behavior:'smooth'});
 }
 async function changeState(row){if(saving||!discard())return;
  if(!confirm((row.active?'Archivar a ':'Reactivar a ')+row.name+'?'+(row.active?' Sus observaciones se conservan.':'')))return;
  saving=true;try{await send('/'+row.id+'/state',{active:!row.active,expected_version:row.version},'PATCH');clearEditor();await reload();await onChanged();message(row.active?'Actor archivado; su historial se conserva.':'Actor reactivado.');}catch(e){message(e.message);}finally{saving=false;}
 }
 async function makePrimary(row){if(saving||!discard()||!confirm('¿Establecer a '+row.name+' como actor principal de este proyecto?'))return;
  const current=data.items.find(x=>x.active&&x.kind==='primary');saving=true;
  try{await send('/'+row.id+'/primary',{expected_version:row.version,previous_primary_id:current?.id??null,previous_primary_version:current?.version??null});
   clearEditor();await reload();await onChanged();message('Actor principal actualizado.');}catch(e){message(e.message);}finally{saving=false;}
 }
 function render(){if(!data)return;const items=data.items,active=items.filter(x=>x.active);
  const refs=active.flatMap(x=>x.channels.filter(c=>c.enabled));
  for(const [id,n] of [['actorsActiveCount',active.length],['actorsChannelCount',refs.length],['actorsReviewCount',refs.filter(c=>c.review!=='reviewed').length],['actorsArchivedCount',items.length-active.length]])byId(id).textContent=n.toLocaleString('es-MX');
  const primary=active.find(x=>x.kind==='primary');byId('actorsPrincipal').textContent=primary?'Actor principal · '+primary.name:'Define el actor principal de este proyecto.';
  byId('actorAdd').hidden=!data.can_manage;
  const term=byId('actorSearch').value.trim().toLocaleLowerCase('es-MX'),state=byId('actorStatusFilter').value;
  const filtered=items.filter(x=>(state==='all'||(state==='active'?x.active:!x.active))&&[x.name,x.public_role,x.organization,x.territory,...x.aliases].join(' ').toLocaleLowerCase('es-MX').includes(term));
  const root=byId('actorsContent');root.replaceChildren();byId('actorsResultCount').textContent=filtered.length+' de '+items.length+' actores';
  for(const row of filtered){const card=el('article',undefined,'actor-directory-card'+(row.kind==='primary'&&row.active?' actor-principal-card':''));
   const initials=row.name.split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();card.append(el('div',initials,'actor-monogram'),el('small',row.active?(row.kind==='primary'?'PRINCIPAL':'COMPARATIVO'):'ARCHIVADO','actor-kind'),el('h3',row.name),el('p',row.public_role||'Actor público','note'));
   if(row.organization||row.territory)card.append(el('p',[row.organization,row.territory].filter(Boolean).join(' · '),'note'));
   card.append(el('p',row.channels.filter(x=>x.enabled).length+' cuentas en seguimiento · '+row.mentions_in_archive.toLocaleString('es-MX')+' menciones en archivo','note'));
   const actions=el('div',undefined,'actions'),detail=el('button','Abrir ficha','outline');detail.type='button';detail.onclick=()=>showDetail(row);actions.append(detail);
   card.append(actions);root.append(card);
  }
  const settings=byId('settingsActors');settings.replaceChildren();
  if(data.can_manage)for(const row of items){const line=el('div',undefined,'settings-record'),identity=el('div');identity.append(el('strong',row.name),el('small',(row.kind==='primary'?'Principal':'Comparativo')+(row.active?'':' · archivado')));line.append(identity);
   const actions=el('div',undefined,'actions'),edit=el('button','Editar ficha','outline');edit.type='button';edit.onclick=()=>openEditor(row);actions.append(edit);
   const state=el('button',row.active?'Archivar':'Reactivar','outline');state.type='button';state.onclick=()=>changeState(row);actions.append(state);
   if(row.active&&row.kind!=='primary'){const primary=el('button','Hacer principal','outline');primary.type='button';primary.onclick=()=>makePrimary(row);actions.append(primary);}line.append(actions);settings.append(line);}
  if(data.can_manage&&!items.length)settings.append(el('p','Registra el actor principal de este proyecto.','note'));
  if(!filtered.length)root.append(el('p',items.length?'No hay actores que coincidan con los filtros.':'Comienza con el actor principal y añade las referencias públicas de este proyecto.','live-empty'));
  if(data.truncated)message('El directorio muestra hasta 50 actores.');
 }
 async function reload(){if(!getProject())return;const pid=getProject(),stamp=++sequence;
  try{const result=await api(base());if(stamp!==sequence||pid!==getProject())return;data=result;render();byId('actorDetail').hidden=true;
   if(!data.can_manage)clearEditor();return result;
  }catch(e){if(stamp===sequence&&pid===getProject())message(e.message);}
 }
 byId('actorAdd').onclick=()=>openEditor();byId('actorCancel').onclick=()=>{if(discard())clearEditor();};
 byId('actorAddChannel').onclick=()=>{if(byId('actorChannels').children.length>=12){byId('actorFormMessage').textContent='Máximo 12 referencias por ficha.';return;}addChannel();dirty=true;};
 byId('actorForm').addEventListener('input',()=>{dirty=true;});byId('actorSearch').addEventListener('input',render);byId('actorStatusFilter').onchange=render;
 byId('actorsRefresh').onclick=reload;
 byId('actorForm').onsubmit=async e=>{e.preventDefault();if(saving||!data?.can_manage)return;const pid=getProject(),editing=selected;byId('actorSave').disabled=true;saving=true;byId('actorFormMessage').textContent='';
  const body={};for(const [id,key] of [['actorName','name'],['actorRole','public_role'],['actorOrganization','organization'],['actorTerritory','territory'],['actorDescription','description']])body[key]=byId(id).value.trim();
  body.aliases=byId('actorAliases').value.split('\n').map(x=>x.trim()).filter(Boolean);body.channels=Array.from(byId('actorChannels').children).map(x=>x.read());
  if(editing){body.expected_actor_version=editing.version;body.expected_profile_version=editing.profile_version;}else body.kind=byId('actorKind').value;
  try{await send(editing?'/'+editing.id:'',body,editing?'PUT':'POST');if(pid!==getProject())return;
   clearEditor();await reload();await onChanged();message('Ficha guardada. Pulso utiliza el mismo actor.');
  }catch(e){if(pid===getProject())byId('actorFormMessage').textContent=e.message;}finally{saving=false;byId('actorSave').disabled=false;}
 };
 function resetProject(){sequence++;data=null;clearEditor();byId('actorsContent').replaceChildren();byId('settingsActors').replaceChildren();byId('actorDetail').replaceChildren();byId('actorDetail').hidden=true;byId('actorSearch').value='';byId('actorStatusFilter').value='active';byId('actorAdd').hidden=true;
  for(const id of ['actorsActiveCount','actorsChannelCount','actorsReviewCount','actorsArchivedCount'])byId(id).textContent='—';byId('actorsPrincipal').textContent='';byId('actorsResultCount').textContent='';message('');}
 return {catalogue:()=>data,reload,resetProject,canLeaveProject:()=>!saving&&discard()};
}};
