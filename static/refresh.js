/* Shared cut metadata is read-only. Only owners can request new collection. */
window.NexoRefresh={install({api,byId,getProject,canManage,onCompleted=async()=>{}}){
 let sequence=0,timer=null,lastCut=null,busy=false,loaded=false;
 const current=(pid,stamp)=>pid===getProject()&&stamp===sequence;
 const date=value=>new Intl.DateTimeFormat('es-MX',{timeZone:'America/Mexico_City',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
 function resetProject(){sequence++;clearTimeout(timer);timer=null;lastCut=null;busy=false;loaded=false;byId('refreshNow').hidden=true;byId('refreshNow').disabled=false;byId('refreshCut').textContent='Corte diario · 08:00 h';byId('refreshFeedback').textContent='';}
 async function reload(){
  const pid=getProject(),stamp=sequence;if(!pid)return;
  try{
   const packet=await api('/api/projects/'+pid+'/refresh');if(!current(pid,stamp))return;
   byId('refreshNow').hidden=!(canManage()&&packet.can_refresh);byId('refreshNow').disabled=busy||packet.running;
   byId('refreshNow').textContent=packet.running?'Actualizando…':'↻ Actualizar datos';
   byId('refreshCut').textContent=packet.last_completed_at?'Último corte: '+date(packet.last_completed_at):'Corte diario · 08:00 h';
   byId('refreshCut').title='Actualización diaria a las 08:00, hora de Aguascalientes';
   const completedRequest=busy&&!packet.running&&['succeeded','partial'].includes(packet.last_status);
   if(!packet.running&&busy){busy=false;byId('refreshFeedback').textContent=['succeeded','partial'].includes(packet.last_status)?'Actualización completada.':'No se completó la actualización. Revisa las fuentes en Configuración.';}
   byId('refreshNow').disabled=busy||packet.running;
   const changed=completedRequest||(loaded&&packet.last_completed_at&&lastCut!==packet.last_completed_at);lastCut=packet.last_completed_at;loaded=true;
   if(changed){await onCompleted();return;}
   clearTimeout(timer);
   const at=new Date(packet.next_scheduled_for).getTime();
   const localHour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'America/Mexico_City',hour:'2-digit',hourCycle:'h23'}).format(new Date()));
   const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
   const doneDay=packet.last_completed_at?new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(packet.last_completed_at)):null;
   const waitingForDaily=localHour>=8&&localHour<10&&doneDay!==today;
   const delay=packet.running?5000:waitingForDaily?60000:Math.max(1000,Math.min(86400000,at-Date.now()+30000));
   timer=setTimeout(()=>reload(),delay);
  }catch(error){if(current(pid,stamp)){if(canManage())byId('refreshFeedback').textContent=error.message;clearTimeout(timer);timer=setTimeout(()=>reload(),60000);}}
 }
 byId('refreshNow').onclick=async()=>{
  if(busy||!canManage())return;const pid=getProject(),stamp=sequence;busy=true;byId('refreshNow').disabled=true;byId('refreshFeedback').textContent='Solicitando actualización…';
  try{await api('/api/projects/'+pid+'/refresh',{method:'POST'});if(current(pid,stamp)){byId('refreshFeedback').textContent='Actualización en curso.';await reload();}}
  catch(error){if(current(pid,stamp)){busy=false;byId('refreshFeedback').textContent=error.message;byId('refreshNow').disabled=false;}}
 };
 return {reload,resetProject};
}};
