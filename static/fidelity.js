/* Atalaya account publication activity, using NEXO's existing session and project. */
window.NexoFidelity={install({api,byId,getProject}){
 const team=window.NexoTeam?.install({api,byId,getProject});
 let sequence=0,scope=null,packet=null,tab='publications',page=0,account='',busy=false,dirty=false;
 const names={facebook:'Facebook',instagram:'Instagram',tiktok:'TikTok',x:'X',youtube:'YouTube',press:'Prensa',other:'Sitio público'};
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const num=v=>v===null||v===undefined?'—':Number(v).toLocaleString('es-MX',{maximumFractionDigits:2});
 const date=v=>new Date(v).toLocaleString('es-MX',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
 const path=()=>'/api/projects/'+getProject()+'/continuity';
 function clear(){team?.invalidate();packet=null;for(const id of ['fidelityPosts','fidelityEngagement','fidelityInteractions','fidelityFollowers','fidelityMentions','fidelityAccountsCount'])byId(id).textContent='—';
  for(const id of ['fidelityAccounts','fidelityRows'])byId(id).replaceChildren();byId('fidelityProvenance').textContent='';byId('fidelityQuality').textContent='';byId('fidelityPager').textContent='';
  byId('fidelityImportPanel').hidden=true;byId('fidelityDownload').disabled=true;byId('fidelityPrev').disabled=true;byId('fidelityNext').disabled=true;}
 function table(){
  const list=packet?.[tab]||[],rows=list.slice(page*8,page*8+8),root=byId('fidelityRows');root.replaceChildren();
  byId('fidelityPublicationsTab').setAttribute('aria-pressed',String(tab==='publications'));byId('fidelityMentionsTab').setAttribute('aria-pressed',String(tab==='mentions'));
  for(const item of rows){const tr=el('tr');const data=[['Fecha',date(item.published_at)],['Red',names[item.network]||item.network],['Publicación',null],
    ['Reacciones',tab==='publications'?num(item.reactions):'—'],['Comentarios',tab==='publications'?num(item.comments):'—'],
    ['Compartidos',tab==='publications'?num(item.shares):'—'],['Interacciones',num(item.interactions)],['Engagement',tab==='publications'?(item.engagement_rate===null?'—':num(item.engagement_rate)+' %'):'—']];
   for(const [label,value] of data){const td=el('td');td.setAttribute('data-label',label);
    if(value===null){const link=el('a',item.text||'Abrir publicación');if(/^https:\/\//i.test(item.url)){link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';}td.append(link);if(item.partial)td.append(el('small','Contadores parciales','fid-partial'));}
    else td.textContent=value;tr.append(td);}root.append(tr);}
  if(!rows.length){const tr=el('tr'),td=el('td',tab==='mentions'&&packet?.mentions_scope==='not_attributed_to_account'?'Elige «Todas las cuentas» para consultar las menciones del actor.':'Sin registros guardados en este periodo.');td.setAttribute('colspan','8');tr.append(td);root.append(tr);}
  byId('fidelityPager').textContent='Página '+(page+1)+' de '+Math.max(1,Math.ceil(list.length/8))+' · '+list.length+' '+(tab==='publications'?'publicaciones':'menciones');
  byId('fidelityPrev').disabled=page===0;byId('fidelityNext').disabled=(page+1)*8>=list.length;
 }
 function render(p){packet=p;const m=p.summary;
  byId('fidelityAccessLabel').textContent=p.can_import?'Administración del proyecto':'Consulta del proyecto';
  for(const [id,key,suffix] of [['fidelityPosts','publications',''],['fidelityEngagement','engagement_rate',' %'],['fidelityInteractions','interactions',''],['fidelityFollowers','followers',''],['fidelityMentions','mentions',''],['fidelityAccountsCount','account_count','']]){
   byId(id).textContent=num(m[key])+(m[key]===null?'':suffix);}
  const root=byId('fidelityAccounts');for(const a of p.registered_accounts){const pill=el('a',p.actor_name+' · '+names[a.network],'fid-account');pill.href=a.url;pill.target='_blank';pill.rel='noopener noreferrer';root.append(pill);}
  if(!p.registered_accounts.length)root.append(el('p',p.actor_id?'Este actor todavía no tiene cuentas registradas.':'Registra el actor principal y sus cuentas desde Actores. Puedes preparar el equipo desde este apartado.','note'));
  byId('fidelityProvenance').textContent=p.source_kind==='synthetic'?'Muestra ficticia · solo revisión local':p.latest_capture?'Exportación de Atalaya · '+date(p.latest_capture):'Archivo del proyecto';
  byId('fidelityQuality').textContent=p.partial_counters?'Interacciones: suma de los contadores disponibles; los campos ausentes se conservan como —.':'';
  if(p.coverage_bounded)byId('fidelityQuality').textContent+=' Consulta acotada al historial disponible.';
  byId('fidelityImportPanel').hidden=!p.can_import||!p.registered_accounts.length;byId('fidelityDownload').disabled=false;
  const select=byId('fidelityAccount'),current=select.value;select.replaceChildren();const all=el('option','Todas las cuentas');all.value='';select.append(all);
  const refs=scope?.accounts||p.registered_accounts;for(const a of refs){const o=el('option',names[a.network]+' · '+a.url);o.value=a.url;select.append(o);}
  select.value=account||'';table();team?.reload({actor_id:p.actor_id,window:p.window,network:byId('continuityNetwork').value,account_url:account,accounts:scope.accounts});
 }
 async function reload(context){scope=context;page=0;const stamp=++sequence,pid=getProject();clear();if(!pid||!context)return;
  if(account&&!context.accounts.some(a=>a.url===account))account='';
  const network=byId('continuityNetwork').value;
  if(!['all','facebook','instagram','tiktok','x','youtube'].includes(network))return;
  byId('fidelityStatus').textContent='Consultando publicaciones…';
  try{const q=new URLSearchParams({...context.window,actor_id:context.selected_actor_id||0,network,account_url:account});
   const p=await api(path()+'/activity?'+q);if(stamp!==sequence||pid!==getProject())return;byId('fidelityStatus').textContent='';render(p);
  }catch(e){if(stamp===sequence&&pid===getProject())byId('fidelityStatus').textContent=e.message;}
 }
 const canonical=value=>{try{const u=new URL(value);return u.protocol+'//'+u.hostname.toLowerCase().replace(/^www\./,'')+u.pathname.replace(/\/+$/,'').toLowerCase();}catch{return '';}};
 function normalize(data,selected){
  if(!data||!Array.isArray(data.publicaciones)||!data.actualizado)throw Error('Elige resultados.json de Atalaya, con publicaciones y fecha de actualización.');
  if(data.publicaciones.length>5000)throw Error('La exportación es demasiado grande; usa un archivo de publicaciones acotado.');
  const aliases={facebook:'facebook',fb:'facebook',instagram:'instagram',ig:'instagram',tiktok:'tiktok',x:'x',twitter:'x',youtube:'youtube'};
  const rows=data.publicaciones.filter(p=>p&&aliases[String(p.red).toLowerCase()]===selected.network&&canonical(p.cuenta)===canonical(selected.url));
  if(!rows.length)throw Error('El archivo no contiene publicaciones de la cuenta elegida.');
  if(rows.length>500)throw Error('Máximo 500 publicaciones de una cuenta por importación.');
  if(rows.some(p=>typeof p.fecha!=='string'||!/(Z|[+-]\d{2}:\d{2})$/.test(p.fecha)||!Number.isFinite(Date.parse(p.fecha))))throw Error('Hay publicaciones sin fecha válida o zona horaria. No se incorporó el archivo.');
  if(typeof data.actualizado!=='string'||!/(Z|[+-]\d{2}:\d{2})$/.test(data.actualizado)||!Number.isFinite(Date.parse(data.actualizado)))throw Error('La fecha de actualización no es válida o no incluye zona horaria.');
  const count=v=>Number.isSafeInteger(v)&&v>=0?v:null;
  // Deliberate whitelist: autores, org, team, historial and stance never enter
  // the outgoing request. Only the public account publication counters do.
  return {contract:'atalaya-publications-v1',actor_id:scope.selected_actor_id,network:selected.network,account_url:selected.url,captured_at:data.actualizado,
   publications:rows.map(p=>({url:p.url,published_at:p.fecha,text:String(p.texto||'').slice(0,1000),
    reactions:count(p.reacciones),comments:count(p.comentarios),shares:count(p.compartidos),followers:count(p.seguidores)}))};
 }
 byId('fidelityAccount').onchange=()=>{account=byId('fidelityAccount').value;reload(scope);};
 byId('fidelityPublicationsTab').onclick=()=>{tab='publications';page=0;table();};byId('fidelityMentionsTab').onclick=()=>{tab='mentions';page=0;table();};
 byId('fidelityPrev').onclick=()=>{page=Math.max(0,page-1);table();};byId('fidelityNext').onclick=()=>{page++;table();};
 byId('fidelityFile').onchange=()=>{dirty=!!byId('fidelityFile').files.length;};
 byId('fidelityImportForm').onsubmit=async e=>{e.preventDefault();if(busy||!packet?.can_import)return;
  const file=byId('fidelityFile').files[0];if(!file)return;
  if(file.size>5_000_000){byId('fidelityImportStatus').textContent='Máximo 5 MB por archivo de origen.';return;}
  const selected=scope.accounts.find(a=>a.url===byId('fidelityImportAccount').value);if(!selected){byId('fidelityImportStatus').textContent='Selecciona una cuenta registrada.';return;}
  const pid=getProject(),stamp=sequence;busy=true;byId('fidelityImportButton').disabled=true;
  try{const data=JSON.parse(await file.text());if(pid!==getProject()||stamp!==sequence)return;
   const body=normalize(data,selected),raw=JSON.stringify(body);if(new TextEncoder().encode(raw).length>1_000_000)throw Error('Máximo 1 MB de publicaciones normalizadas.');
   const r=await api(path()+'/atalaya/import',{method:'POST',headers:{'Content-Type':'application/json'},body:raw});
   if(pid!==getProject())return;dirty=false;byId('fidelityFile').value='';await reload(scope);byId('fidelityImportStatus').textContent=r.duplicates?'Esta captura ya estaba incorporada.':'Publicaciones incorporadas. No se importaron perfiles o rankings.';
  }catch(e){if(pid===getProject())byId('fidelityImportStatus').textContent=e instanceof SyntaxError?'El archivo no contiene JSON válido.':e.message;}
  finally{busy=false;byId('fidelityImportButton').disabled=false;}
 };
 byId('fidelityImportPanel').ontoggle=()=>{if(!packet?.can_import)return;const select=byId('fidelityImportAccount');select.replaceChildren();for(const a of scope.accounts){const o=el('option',names[a.network]+' · '+a.url);o.value=a.url;select.append(o);}};
 byId('fidelityDownload').onclick=()=>{if(!packet)return;const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)],{type:'application/json'})),link=el('a');link.href=url;link.download='NEXO_Fidelidad_Corte.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 function reset(){team?.reset();sequence++;scope=null;account='';tab='publications';page=0;dirty=false;clear();byId('fidelityStatus').textContent='';byId('fidelityFile').value='';byId('fidelityImportStatus').textContent='';byId('fidelityAccount').replaceChildren();byId('fidelityImportAccount').replaceChildren();}
 return{reload,reset,normalize,invalidate:()=>{sequence++;clear();byId('fidelityStatus').textContent='';},canLeaveProject:()=>!busy&&(team?.canLeaveProject()??true)&&(!dirty||confirm('Hay un archivo de Atalaya sin incorporar. ¿Descartarlo al cambiar de proyecto?'))};
}};
