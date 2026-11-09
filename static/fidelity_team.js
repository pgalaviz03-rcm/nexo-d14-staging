/* Collaborators explicitly registered by the owner; no organic identity table. */
window.NexoTeam={install({api,byId,getProject}){
 let seq=0,scope=null,packet=null,roster=[],owner=false,busy=false,dirty=false,sourceDirty=false,memberDirty=false,tab='team',sort='posts',page=0,profileSeq=0,profileMember=0,profilePage=1;
 const names={facebook:'Facebook',instagram:'Instagram',tiktok:'TikTok',x:'X'};
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const num=v=>v===null||v===undefined?'—':Number(v).toLocaleString('es-MX',{maximumFractionDigits:1});
 const url=()=>'/api/projects/'+getProject()+'/continuity/team';
 function clear(){closeProfile();packet=null;owner=false;roster=[];byId('teamManagePanel').hidden=true;byId('teamRows').replaceChildren();byId('teamRosterList').replaceChildren();byId('teamCommunity').replaceChildren();byId('teamStatus').textContent='';byId('teamSummary').textContent='';byId('teamPager').textContent='';byId('teamPrev').disabled=true;byId('teamNext').disabled=true;}
 function table(){
  const list=[...(packet?.rows||[])],rank=sort==='reactions'?'reaction_posts':sort==='comments'?'comment_posts':'participated_posts';
  list.sort((a,b)=>b[rank]-a[rank]||a.name.localeCompare(b.name));const root=byId('teamRows');root.replaceChildren();
  list.slice(page*10,page*10+10).forEach((r,i)=>{const tr=el('tr');for(const [label,value] of [['#',page*10+i+1],['Integrante',r.name],['Redes',r.networks.map(n=>names[n]).join(' · ')],
    ['Reacciones registradas',num(r.reaction_posts)],['Publicaciones comentadas',num(r.comment_posts)],['Comentarios',num(r.comment_events)],
    ['Presencia registrada',r.participation_percent===null?'—':num(r.participation_percent)+' % · '+r.participated_posts+'/'+r.eligible_posts],
    ['Última observación',r.last_observed?new Date(r.last_observed).toLocaleString('es-MX',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'—']]){
    const td=el('td');if(label==='Integrante'){const button=el('button',r.name,'team-member-link');button.type='button';button.onclick=()=>openProfile(r.member_id,1);td.append(button);}else td.textContent=String(value);td.setAttribute('data-label',label);tr.append(td);}root.append(tr);});
  if(!list.length){const tr=el('tr'),td=el('td',owner?'Añade integrantes desde Configuración → Equipo.':'Aún no hay integrantes registrados en este proyecto.');td.setAttribute('colspan','8');tr.append(td);root.append(tr);}
  byId('teamPager').textContent='Página '+(page+1)+' de '+Math.max(1,Math.ceil(list.length/10))+' · '+list.length+' integrantes';
  byId('teamPrev').disabled=page===0;byId('teamNext').disabled=(page+1)*10>=list.length;
 }
 function closeProfile(){profileSeq++;profileMember=0;profilePage=1;byId('teamProfilePanel').hidden=true;byId('teamProfileAccounts').replaceChildren();byId('teamProfileItems').replaceChildren();for(const id of ['teamProfileName','teamProfileStatus','teamProfileSummary','teamProfilePager'])byId(id).textContent='';}
 async function openProfile(member,page=1){const stamp=++profileSeq,pid=getProject(),generation=seq;profileMember=member;profilePage=page;byId('teamProfilePanel').hidden=false;byId('teamProfileStatus').textContent='Consultando las acciones registradas…';
  try{const q=new URLSearchParams({...scope.window,actor_id:scope.actor_id||0,network:scope.network||'all',account_url:scope.account_url||'',page});
   const p=await api(url()+'/'+member+'/profile?'+q);if(stamp!==profileSeq||pid!==getProject()||generation!==seq)return;
   byId('teamProfileName').textContent=p.name;byId('teamProfileStatus').textContent='';const links=byId('teamProfileAccounts');links.replaceChildren();
   for(const a of p.accounts){const link=el('a',names[a.network],'outline');link.href=a.url;link.target='_blank';link.rel='noopener noreferrer';links.append(link);}
   const m=p.summary;byId('teamProfileSummary').textContent=m.reaction_posts+' publicaciones con reacción · '+m.comment_posts+' publicaciones comentadas · '+(m.comment_events===null?'Sin desglose individual de comentarios':m.comment_events+' comentarios registrados')+(p.actor_name?' · '+p.actor_name:'');
   const root=byId('teamProfileItems');root.replaceChildren();for(const row of p.items){const card=el('div',undefined,'team-profile-item'),link=el('a',row.text||'Abrir publicación');link.href=row.url;link.target='_blank';link.rel='noopener noreferrer';card.append(link,el('p',names[row.network]+' · '+new Date(row.published_at).toLocaleString('es-MX'),'note'));
    const parts=[];if(row.reaction_recorded)parts.push('Reacción registrada');if(row.comment_recorded)parts.push(row.identified_comments?row.identified_comments+' comentarios':'Comentario registrado');card.append(el('p',parts.join(' · ')),el('small','Observado: '+new Date(row.last_observed).toLocaleString('es-MX')));root.append(card);}
   if(!p.items.length)root.append(el('p','Sin acciones registradas en las publicaciones de este corte.','note'));
   byId('teamProfilePager').textContent='Página '+p.page+' de '+Math.max(1,Math.ceil(p.total_publications/p.page_size));byId('teamProfilePrev').disabled=p.page<=1;byId('teamProfileNext').disabled=p.page*p.page_size>=p.total_publications;byId('teamProfilePanel').scrollIntoView?.({block:'nearest',behavior:'smooth'});
  }catch(e){if(stamp===profileSeq&&pid===getProject())byId('teamProfileStatus').textContent=e.message;}
 }
 byId('teamProfileClose').onclick=closeProfile;byId('teamProfilePrev').onclick=()=>{if(profileMember&&profilePage>1)openProfile(profileMember,profilePage-1);};byId('teamProfileNext').onclick=()=>{if(profileMember)openProfile(profileMember,profilePage+1);};
 function render(p){packet=p;owner=!!p.can_manage;
  byId('teamSummary').textContent=p.summary.members+' integrantes · '+p.summary.members_with_records+' con actividad registrada en publicaciones del periodo';
  byId('teamManagePanel').hidden=!owner;
  const root=byId('teamCommunity');root.replaceChildren();
  for(const [label,key] of [['Reacciones disponibles','reactions'],['Comentarios disponibles','comments'],['Compartidos disponibles','shares']]){
   const card=el('div');card.append(el('span',label),el('strong',num(p.community[key])));root.append(card);}
  table();showTab();syncAccounts();
 }
 function showTab(){byId('teamTablePanel').hidden=tab!=='team';byId('teamCommunityPanel').hidden=tab!=='community';
  byId('teamTab').setAttribute('aria-pressed',String(tab==='team'));byId('teamCommunityTab').setAttribute('aria-pressed',String(tab==='community'));}
 async function loadRoster(stamp,pid){
  if(!owner)return;const p=await api(url()+'/roster');if(stamp!==seq||pid!==getProject())return;roster=p.items;
  const root=byId('teamRosterList');root.replaceChildren();
  for(const m of roster){const row=el('div',undefined,'team-roster-row');row.append(el('span',m.name+' · '+Object.keys(m.profiles).map(n=>names[n]).join(' / ')+(m.active?'':' · inactivo')));
   const button=el('button',m.active?'Desactivar':'Reactivar','outline');button.type='button';
   button.onclick=async()=>{if(busy)return;busy=true;try{await api(url()+'/'+m.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({active:!m.active})});await reload(scope);}catch(e){byId('teamImportStatus').textContent=e.message;}finally{busy=false;}};
   row.append(button);root.append(row);}
 }
 async function reload(context){scope=context;page=0;const stamp=++seq,pid=getProject();clear();if(!pid||!context)return;
  try{const q=new URLSearchParams({...context.window,actor_id:context.actor_id||0,network:context.network||'all',account_url:context.account_url||''});
   const p=await api(url()+'?'+q);if(stamp!==seq||pid!==getProject())return;render(p);await loadRoster(stamp,pid);
  }catch(e){if(stamp===seq&&pid===getProject())byId('teamStatus').textContent=e.message;}
 }
 function profileKey(network,value){
  let v=String(value||'').trim();if(!v)return '';if(network==='facebook'&&/^id:[0-9]+$/.test(v))return v;
  if(/^https?:\/\//i.test(v)){try{const u=new URL(v);const host=u.hostname.toLowerCase().replace(/^(www|m|mobile|web)\./,'');const expected={facebook:'facebook.com',instagram:'instagram.com',tiktok:'tiktok.com',x:'x.com'}[network];if(u.protocol!=='https:'||u.username||u.password||!(host===expected||(network==='x'&&host==='twitter.com')))return '';if(network==='facebook'&&u.pathname.replace(/\/+$/,'')==='/profile.php'){const id=u.searchParams.get('id');return /^[0-9]+$/.test(id||'')?'id:'+id:'';}v=u.pathname.split('/').filter(Boolean)[0]||'';}catch{return '';}}
  v=v.replace(/^@/,'').toLowerCase();return /^[a-z0-9_.-]{1,100}$/.test(v)?v:'';
 }
 const canonical=value=>{try{const u=new URL(value);return u.protocol+'//'+u.hostname.toLowerCase().replace(/^www\./,'')+u.pathname.replace(/\/+$/,'').toLowerCase()+u.search;}catch{return '';}};
 function normalizeAtalaya(data,selected){
  if(!Array.isArray(data?.publicaciones)||!data.actualizado)throw Error('Elige resultados.json de Atalaya.');
  const aliases={fb:'facebook',facebook:'facebook',ig:'instagram',instagram:'instagram',tt:'tiktok',tiktok:'tiktok',x:'x',twitter:'x'};
  const mapping=new Map();for(const m of roster.filter(m=>m.active))for(const [n,key] of Object.entries(m.profiles))mapping.set(n+':'+key,m.id);
  const events=[],seen=new Set();let omitted=0;
  for(const p of data.publicaciones){
   const network=aliases[String(p.red).toLowerCase()];if(network!==selected.network||canonical(p.cuenta)!==canonical(selected.url))continue;
   if(!Array.isArray(p.autores))continue;
   for(const a of p.autores){if(!Array.isArray(a)||a.length<4)continue;
    const authorNetwork=aliases[String(a[0]).toLowerCase()];if(authorNetwork!==network)continue;
    const mid=mapping.get(network+':'+profileKey(network,a[1]));if(!mid){omitted++;continue;}
    const kind=a[3]==='comentario'?'comment_presence':a[3]==='reaccion'?'reaction':null;if(!kind)continue;
    const key=[mid,network,p.url,kind].join('|');if(seen.has(key))continue;seen.add(key);
    events.push({member_id:mid,network,post_url:p.url,kind,event_id:'',observed_at:data.actualizado});
   }}
  if(events.length>5000)throw Error('Máximo 5000 observaciones por lote.');
  return{body:{actor_id:scope.actor_id,events},omitted};
 }
 byId('teamTab').onclick=()=>{tab='team';showTab();};byId('teamCommunityTab').onclick=()=>{tab='community';showTab();};
 byId('teamSort').onchange=()=>{sort=byId('teamSort').value;page=0;table();};byId('teamPrev').onclick=()=>{page=Math.max(0,page-1);table();};byId('teamNext').onclick=()=>{page++;table();};
 byId('teamRosterFile').onchange=()=>{dirty=!!byId('teamRosterFile').files.length;};byId('teamSourceFile').onchange=()=>{sourceDirty=!!byId('teamSourceFile').files.length;};
 const memberFields={name:'teamMemberName',code:'teamMemberCode',facebook:'teamMemberFacebook',instagram:'teamMemberInstagram',tiktok:'teamMemberTiktok',x:'teamMemberX'};
 function clearMember(){memberDirty=false;for(const id of Object.values(memberFields))byId(id).value='';}
 for(const id of Object.values(memberFields))byId(id).oninput=()=>{memberDirty=Object.values(memberFields).some(key=>byId(key).value.trim());};
 byId('teamMemberForm').onsubmit=async e=>{e.preventDefault();if(busy||!owner)return;
  const body=Object.fromEntries(Object.entries(memberFields).map(([k,id])=>[k,byId(id).value.trim()]));
  if(!body.name||!['facebook','instagram','tiktok','x'].some(k=>body[k])){byId('teamMemberStatus').textContent='Escribe el nombre y al menos una cuenta.';return;}
  const pid=getProject();busy=true;byId('teamMemberButton').disabled=true;
  try{const p=await api(url()+'/roster/member',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   if(pid!==getProject())return;clearMember();await reload(scope);byId('teamMemberStatus').textContent=p.inserted?'Integrante registrado.':p.updated?'Ficha del integrante actualizada.':'El integrante ya estaba registrado con esos datos.';
  }catch(e){if(pid===getProject())byId('teamMemberStatus').textContent=e.message;}finally{busy=false;byId('teamMemberButton').disabled=false;}
 };
 byId('teamRosterForm').onsubmit=async e=>{e.preventDefault();if(busy||!owner)return;const file=byId('teamRosterFile').files[0];if(!file)return;
  if(file.size>2*1024*1024){byId('teamImportStatus').textContent='Máximo 2 MB por Excel o CSV.';return;}
  const pid=getProject();busy=true;byId('teamRosterButton').disabled=true;
  try{const form=new FormData();form.append('file',file);form.append('sheet',byId('teamSheet').value.trim());
   const p=await api(url()+'/roster/import',{method:'POST',body:form});if(pid!==getProject())return;
   dirty=false;byId('teamRosterFile').value='';await reload(scope);byId('teamImportStatus').textContent=p.inserted+' nuevos · '+p.updated+' actualizados · '+p.unchanged+' sin cambios.';
  }catch(e){if(pid===getProject())byId('teamImportStatus').textContent=e.message;}finally{busy=false;byId('teamRosterButton').disabled=false;}
 };
 byId('teamSourceForm').onsubmit=async e=>{e.preventDefault();if(busy||!owner)return;const file=byId('teamSourceFile').files[0];if(!file)return;
  if(file.size>5_000_000){byId('teamActivityStatus').textContent='Máximo 5 MB por archivo.';return;}
  const selected=scope.accounts.find(a=>a.url===byId('teamSourceAccount').value);if(!selected){byId('teamActivityStatus').textContent='Selecciona una cuenta del actor.';return;}
  const stamp=seq,pid=getProject();busy=true;byId('teamSourceButton').disabled=true;
  try{const data=JSON.parse(await file.text());if(stamp!==seq||pid!==getProject())return;const normalized=normalizeAtalaya(data,selected);
   if(!normalized.body.events.length)throw Error('No hay coincidencias exactas con las cuentas activas del equipo. No se asigna actividad por nombre.');
   const raw=JSON.stringify(normalized.body);if(new TextEncoder().encode(raw).length>1_000_000)throw Error('Máximo 1 MB de observaciones del equipo.');
   const r=await api(url()+'/events',{method:'POST',headers:{'Content-Type':'application/json'},body:raw});
   if(pid!==getProject())return;sourceDirty=false;byId('teamSourceFile').value='';await reload(scope);
   byId('teamActivityStatus').textContent=r.inserted+' registros nuevos · '+r.duplicates+' ya observados. Solo se incorporaron coincidencias del equipo.';
  }catch(e){if(pid===getProject())byId('teamActivityStatus').textContent=e instanceof SyntaxError?'El archivo no contiene JSON válido.':e.message;}
  finally{busy=false;byId('teamSourceButton').disabled=false;}
 };
 function syncAccounts(){if(!owner)return;const ready=!!scope.accounts?.length;byId('teamSourceForm').hidden=!ready;byId('teamAccountSetup').hidden=ready;const select=byId('teamSourceAccount');select.replaceChildren();for(const a of scope.accounts||[]){const o=el('option',names[a.network]+' · '+a.url);o.value=a.url;select.append(o);}}
 byId('teamManagePanel').ontoggle=syncAccounts;
 byId('teamTemplate').onclick=async()=>{if(!owner)return;try{const p=await api(url()+'/template'),href=URL.createObjectURL(new Blob([p.csv_text],{type:'text/csv;charset=utf-8'})),a=el('a');a.href=href;a.download=p.filename;a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);}catch(e){byId('teamImportStatus').textContent=e.message;}};
 function reset(){seq++;scope=null;clearMember();byId('teamMemberStatus').textContent='';dirty=false;sourceDirty=false;page=0;tab='team';clear();for(const id of ['teamRosterFile','teamSourceFile','teamSheet'])byId(id).value='';byId('teamImportStatus').textContent='';byId('teamActivityStatus').textContent='';byId('teamSourceAccount').replaceChildren();}
 return{reload,reset,normalizeAtalaya,profileKey,invalidate:()=>{seq++;clear();},canLeaveProject:()=>!busy&&(!(dirty||sourceDirty||memberDirty)||confirm('Hay cambios del equipo sin guardar. ¿Descartarlos al cambiar de proyecto?'))};
}};
