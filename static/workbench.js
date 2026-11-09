/* Project module views reuse the same authenticated public-content contracts. */
window.NexoWorkbench={install({api,byId,getProject}){
 let sequence=0;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const number=n=>n===null||n===undefined?'Sin dato':Number(n).toLocaleString('es-MX');
 function resetProject(){sequence++;for(const id of ['actorsContent','networksContent','alertsContent','accountAuditContent'])byId(id).replaceChildren();}
 async function reload(name){
  const target={actors:'actorsContent',networks:'networksContent',alerts:'alertsContent',accountAudit:'accountAuditContent'}[name];
  if(!target||!getProject())return;
  const stamp=++sequence,pid=getProject(),root=byId(target);root.replaceChildren(el('p','Consultando el archivo del proyecto…','note'));
  try{
   const config=await api('/api/projects/'+pid+'/pulse/config');
   if(stamp!==sequence||pid!==getProject())return;
   root.replaceChildren();
   if(name==='actors'){
    const actors=config.actors.filter(x=>!x.is_demo);
    if(!actors.length)root.append(el('p','Todavía no se han registrado actores públicos en este proyecto.','hint'));
    for(const a of actors){const card=el('article',undefined,'panel');card.append(el('h3',a.name),el('p',(a.kind==='primary'?'Principal':'Comparativo')+' · '+(a.active?'Activo':'Archivado'),'note'));root.append(card);}
    return;
   }
   const end=new Date(),start=new Date(end.getTime()-86400000*(name==='alerts'?1:30));
   const q=new URLSearchParams({start:start.toISOString(),end:end.toISOString(),demo:'false',network:'all',actor_id:'0'});
   const packet=await api('/api/projects/'+pid+'/pulse?'+q);
   if(stamp!==sequence||pid!==getProject())return;
   if(name==='alerts'){
    root.append(el('p','Corte de últimas 24 horas · '+packet.rules_configured+' reglas activas · '+packet.alerts_evaluated+' evaluables.','note'));
    for(const a of packet.alerts){root.append(el('p',a.name+' · Umbral alcanzado: '+number(a.value)+' / '+number(a.threshold),'pulse-alert'));}
    if(!packet.alerts.length)root.append(el('p',packet.rules_configured?'Sin activaciones en las reglas evaluables; las restantes requieren más datos.':'Sin reglas configuradas para los actores de este corte.','hint'));
    return;
   }
   root.append(el('p','Cuenta principal · Capturas disponibles al cierre de los últimos 30 días. No se agregan audiencias entre redes.','note'));
   for(const a of packet.accounts){const card=el('article',undefined,'panel');card.append(el('h3',a.network),el('p',a.url,'note'));
    if(name==='networks')for(const [key,label] of [['followers','Seguidores'],['posts','Publicaciones'],['views','Vistas'],['reach','Alcance único'],['interactions','Interacciones']])card.append(el('p',label+': '+number(a.metrics[key])));
    else{const missing=['followers','posts','views','reach','interactions'].filter(key=>a.metrics[key]===null||a.metrics[key]===undefined);card.append(el('p','Captura: '+a.captured_at),el('p','Campos sin dato: '+(missing.join(', ')||'ninguno')),el('p',a.stale?'Captura anterior al periodo.':'Captura dentro del periodo.'),el('p',a.metrics.metrics_from?'Periodo declarado: '+a.metrics.metrics_from+' a '+a.metrics.metrics_to:'Sin periodo de métricas declarado.'));}
    root.append(card);
   }
   if(!packet.accounts.length)root.append(el('p','Sin capturas de cuentas públicas. Registra la cuenta principal y una captura desde Pulso.','hint'));
  }catch(e){if(stamp===sequence&&pid===getProject())root.replaceChildren(el('p',e.message,'note'));}
 }
 return {reload,resetProject};
}};
