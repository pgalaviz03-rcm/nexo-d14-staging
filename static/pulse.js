/* PULSO: measured aggregates from project APIs. No provider secrets or calls. */
window.NexoPulse={install({api,byId,getProject}){
 let configDirty=false;
 let config=null,actor=0,mode='real',sequence=0,period='24h';
 const label={positive:'Favorable',neutral:'Neutral',negative:'Desfavorable',joy:'Alegría',anger:'Ira',sadness:'Tristeza',fear:'Miedo',surprise:'Sorpresa'};
 const channels={press:'Prensa',facebook:'Facebook',instagram:'Instagram',x:'X',tiktok:'TikTok',youtube:'YouTube',other:'Otro'};
 const fmt=v=>v===null||v===undefined?'—':Number(v).toLocaleString('es-MX',{maximumFractionDigits:2});
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const path=()=>`/api/projects/${getProject()}/pulse`;
 const status=text=>{byId('pulseStatus').textContent=text;byId('settingsPulseStatus').textContent=text;};
 function range(){
  if(period==='custom'){
   const a=byId('pulseStart').value,b=byId('pulseEnd').value;
   if(!a||!b)throw Error('Completa las dos fechas del periodo.');
   const start=new Date(a+'T00:00:00'),end=new Date(b+'T00:00:00');end.setDate(end.getDate()+1);
   return {start:start.toISOString(),end:end.toISOString()};
  }
  const end=new Date(),days=period==='7d'?7:period==='30d'?30:1;
  return {start:new Date(end.getTime()-days*86400000).toISOString(),end:end.toISOString()};
 }
 function clear(){
  byId('pulseTitle').textContent='Pulso del proyecto';byId('pulseAbout').textContent='TONO DEL CONTENIDO OBSERVADO';byId('pulseFreshness').textContent='';byId('pulseMethod').textContent='';byId('pulseAlertScope').textContent='Esperando consulta';
  for(const id of ['pulseMentions','pulseShare','pulseDelta','pulseAlertsCount','pulseScore'])byId(id).textContent='—';
  for(const id of ['pulseActorFilters','pulseActorCards','pulseEmotions','pulseHeadlines','pulseAccounts','pulseAlertsList','pulseToneBreakdown'])byId(id).replaceChildren();
  byId('pulseScoreLabel').textContent='Sin datos de clasificación';byId('pulseCoverage').textContent='Esperando consulta del archivo.';
  byId('pulseToneComparison').hidden=true;byId('pulseReading').textContent='';byId('pulseAccountName').textContent='';byId('pulseWindowLabel').textContent='Corte seleccionado';byId('pulseMarker').hidden=true;byId('pulseSample').hidden=mode!=='demo';
 }
 const pct=v=>Number(v).toLocaleString('es-MX',{maximumFractionDigits:1});
 const shortDate=value=>new Date(value).toLocaleDateString('es-MX',{day:'numeric',month:'short'});
 const captureDate=value=>new Date(value).toLocaleString('es-MX',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
 const toneName=m=>m.score===null?'Por clasificar':m.positive>m.negative?'Favorable':m.negative>m.positive?'Desfavorable':'Mixto';
 function render(packet){
  const m=packet.metrics,selected=packet.actors.find(x=>x.id===actor),name=selected?.name||'Todos los actores';
  byId('pulseTitle').textContent=config.project.name+(packet.territory?' · '+packet.territory:'');
  byId('pulseWindowLabel').textContent=shortDate(packet.window.start)+' — '+shortDate(packet.window.end);
  const mostPresent=actor?null:[...packet.actors].sort((a,b)=>(b.share||0)-(a.share||0))[0];
  const share=mostPresent?mostPresent.share:m.share;
  byId('pulseMentions').textContent=fmt(m.mentions);byId('pulseShare').textContent=share===null?'—':pct(share)+' %';
  byId('pulseShareLabel').textContent=mostPresent?'Mayor presencia':'Parte de la conversación';
  byId('pulseShareAbout').textContent=mostPresent?mostPresent.name:'Entre los actores monitoreados';
  byId('pulseDelta').textContent=m.score===null||!m.classified?'—':pct(100*m.positive/m.classified)+' %';
  byId('pulseAlertsCount').textContent=fmt(packet.active_alerts);
  byId('pulseAlertScope').textContent=packet.active_alerts===null?'En espera de evaluación':packet.active_alerts===0?'Sin alertas activas':'Requieren revisión';
  byId('pulseScore').textContent=m.score===null?'—':String(Math.round(m.score));
  byId('pulseScoreLabel').textContent=m.score===null?'Esperando clasificación':toneName(m)==='Mixto'?'Conversación mixta':'Tono '+toneName(m).toLocaleLowerCase();
  byId('pulseAbout').textContent='EN FOCO · '+name.toLocaleUpperCase('es-MX');
  byId('pulseReading').textContent=m.score===null?'El índice aparecerá con contenido clasificado suficiente.':
   pct(100*m.positive/m.classified)+' % favorable · '+pct(100*m.negative/m.classified)+' % desfavorable';
  byId('pulseCoverage').textContent=fmt(m.classified)+' de '+fmt(m.mentions)+' menciones clasificadas. Describe contenido público, no una encuesta.';
  const comparison=byId('pulseToneComparison');comparison.hidden=m.score_delta===null;
  if(m.score_delta!==null){const w=packet.comparison_window||{start:new Date(new Date(packet.window.start)-90*86400000),end:packet.window.start};
   comparison.textContent=(m.score_delta>0?'↑ ':m.score_delta<0?'↓ ':'')+pct(Math.abs(m.score_delta))+' puntos '+(m.score_delta>0?'más':m.score_delta<0?'menos':'de diferencia')+' frente al histórico · '+shortDate(w.start)+' — '+shortDate(w.end);}
  byId('pulseMarker').hidden=m.score===null;if(m.score!==null)byId('pulseMarker').style.left=m.score+'%';
  const breakdown=byId('pulseToneBreakdown');breakdown.replaceChildren();
  for(const [key,text] of [['positive','Favorable'],['neutral','Neutral'],['negative','Desfavorable']]){const row=el('div',undefined,'pulse-tone-pill tone-'+key);
   row.append(el('span',text),el('b',m.score===null?'—':pct(100*m[key]/m.classified)+' %'));breakdown.append(row);}
  const chips=byId('pulseActorFilters');chips.replaceChildren();
  for(const item of [{id:0,name:'Todos los actores'},...packet.actors]){
   const button=el('button',item.name,'pulse-chip');button.type='button';button.setAttribute('aria-pressed',String(actor===item.id));
   button.onclick=()=>{actor=item.id;loadDashboard().catch(e=>status(e.message));};chips.append(button);}
  const cards=byId('pulseActorCards');cards.replaceChildren();
  for(const item of packet.actors){const button=el('button',undefined,'pulse-actor-card');button.type='button';button.setAttribute('aria-pressed',String(actor===item.id));
   const avatar=el('span',item.name.split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join(''),'pulse-actor-avatar');
   const identity=el('div',undefined,'pulse-actor-identity');identity.append(el('b',item.name),el('small',item.kind==='primary'?'Actor principal':'Comparativo'));
   const score=el('div',undefined,'pulse-actor-score');score.append(el('b',item.score===null?'—':String(Math.round(item.score))),el('small','índice /100'));
   const meta=el('div',undefined,'pulse-actor-meta');meta.append(el('span',fmt(item.mentions)+' menciones'),el('b',item.share===null?'—':pct(item.share)+' % de conversación'));
   const track=el('div',undefined,'pulse-share-track'),fill=el('span');fill.style.width=Math.max(0,Math.min(100,item.share||0))+'%';track.append(fill);
   button.append(avatar,identity,score,meta,track);button.onclick=()=>{actor=item.id;loadDashboard().catch(e=>status(e.message));};cards.append(button);}
  if(!packet.actors.length)cards.append(el('p','Los actores de este proyecto aparecerán aquí.','note'));
  const emotions=byId('pulseEmotions');emotions.replaceChildren();
  const emotionSymbols={joy:'☀',anger:'ϟ',sadness:'☂',fear:'◈',surprise:'✦'};
  for(const row of packet.emotions){const line=el('div',undefined,'pulse-emotion emotion-'+row.emotion);const bar=el('div',undefined,'pulse-emotion-track'),fill=el('div');fill.style.width=row.percentage+'%';bar.append(fill);
   line.append(el('span',(emotionSymbols[row.emotion]||'◦')+' '+(label[row.emotion]||row.emotion)),bar,el('span',pct(row.percentage)+' %'));emotions.append(line);}
  if(!packet.emotions.length)emotions.append(el('p','Las emociones aparecerán con las primeras clasificaciones.','pulse-soft'));
  const headlines=byId('pulseHeadlines');headlines.replaceChildren();let rank=0;
  for(const item of packet.headlines){const row=el('article',undefined,'pulse-headline'),body=el('div');
   const link=el('a',item.title);if(/^https:\/\//i.test(item.url)){link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';}
   body.append(link,el('small',(item.source||channels[item.network]||item.network)+' · '+captureDate(item.published_at)));
   row.append(el('span',String(++rank).padStart(2,'0'),'pulse-news-number'),body,el('span','↗','pulse-news-arrow'));headlines.append(row);}
  if(!packet.headlines.length)headlines.append(el('p','No hay publicaciones guardadas para este periodo y canal.','note'));
  const accountActor=packet.actors.find(x=>x.id===packet.account_actor_id);byId('pulseAccountName').textContent=accountActor?.name||selected?.name||'Cuenta principal del proyecto';
  const accounts=byId('pulseAccounts');accounts.replaceChildren();
  for(const item of packet.accounts){const card=el('article',undefined,'pulse-account'),head=el('div',undefined,'pulse-account-heading');
   head.append(el('span',({facebook:'f',instagram:'◎',x:'𝕏',youtube:'▶',tiktok:'♪'})[item.network]||'◉','pulse-network-icon'),el('h3',channels[item.network]||item.network));
   if(/^https:\/\//i.test(item.url)){const link=el('a','Ver cuenta ↗');link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';head.append(link);}card.append(head);
   const metrics=el('div',undefined,'pulse-account-metrics');for(const [key,text] of [['followers','Seguidores'],['posts','Publicaciones'],['interactions','Interacciones']]){
    const row=el('div',undefined,'pulse-account-row');row.append(el('span',text),el('b',fmt(item.metrics[key])));metrics.append(row);}card.append(metrics);
   const foot=el('div',undefined,'pulse-account-foot');foot.append(el('small','Actualización · '+captureDate(item.captured_at)));
   if(item.followers_delta!==null&&item.followers_delta!==undefined&&item.baseline_at)foot.append(el('small',(item.followers_delta>0?'+':'')+fmt(item.followers_delta)+' seguidores desde '+shortDate(item.baseline_at)));
   if(item.metrics.metrics_from&&item.metrics.metrics_to)foot.append(el('small','Actividad · '+shortDate(item.metrics.metrics_from)+' — '+shortDate(item.metrics.metrics_to)));
   if(item.stale)foot.append(el('small','Último registro anterior al periodo elegido.'));card.append(foot);accounts.append(card);}
  if(!packet.accounts.length)accounts.append(el('p','Las estadísticas aparecerán con la primera captura de estas cuentas.','note'));
  const alerts=byId('pulseAlertsList');alerts.replaceChildren();
  for(const item of packet.alerts){const row=el('div',undefined,'pulse-alert'),content=el('div');content.append(el('b',item.name),el('small',fmt(item.value)+(item.metric==='negative_share'?' % desfavorable':item.metric==='mentions'?' menciones':' % de aumento')));row.append(el('span','!','pulse-alert-icon'),content);alerts.append(row);}
  if(!packet.alerts.length)alerts.append(el('p',packet.active_alerts===null?'Las alertas aparecerán al evaluar el contenido del corte.':'Sin alertas activas en este corte.','pulse-alert-empty'));
  byId('pulseMethod').textContent=packet.methods.score+'. Universo: '+packet.methods.share+' Comparación: '+packet.methods.baseline+' '+packet.methods.interpretation;
  byId('pulseFreshness').textContent=packet.latest_collection?'Contenido actualizado · '+captureDate(packet.latest_collection):'';
  byId('pulseSample').hidden=!packet.is_demo;status('');
 }
 async function loadDashboard(){
  if(!getProject()||!config)return;
  const token=++sequence,project=getProject();clear();status('Consultando el archivo de este proyecto…');
  const query=new URLSearchParams({...range(),actor_id:actor,network:byId('pulseNetwork').value,demo:mode==='demo'});
  const packet=await api(path()+'?'+query);if(token!==sequence||project!==getProject())return;render(packet);
 }
 async function reload(){
  if(!getProject())return;
  const project=getProject(),token=++sequence,previousVersion=config?.version;config=null;clear();
  const result=await api(path()+'/config');if(token!==sequence||project!==getProject())return;
  config=configDirty&&previousVersion!==undefined?{...result,version:previousVersion}:result;
  byId('pulseConfigForm').hidden=!result.can_manage;byId('pulseImportForm').hidden=!result.can_import;byId('pulseClassification').hidden=!result.can_import;
  mode=result.visual_review?'demo':'real';
  if(!configDirty){byId('pulseTerritory').value=result.territory;byId('pulseMin').value=result.min_classified;}

  if(actor&&!result.actors.some(a=>a.id===actor&&a.is_demo===(mode==='demo')&&a.active))actor=0;
  await loadDashboard();return result;
 }
 const send=async(url,body,method='POST')=>api(path()+url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 byId('pulseConfigForm').oninput=()=>{configDirty=true;};
 byId('pulseConfigForm').onsubmit=async event=>{event.preventDefault();try{
  await send('/config',{territory:byId('pulseTerritory').value,min_classified:Number(byId('pulseMin').value),expected_version:config.version,
   connector:config.connector},'PUT');configDirty=false;await reload();status('Configuración guardada.');
 }catch(e){status(e.message);}};
 byId('pulseImportForm').onsubmit=async event=>{event.preventDefault();try{
  const importProject=getProject();
  const file=byId('pulseImportFile').files[0];if(!file||file.size>2000000)throw Error('Selecciona un JSON normalizado de hasta 2 MB.');
  const data=JSON.parse(await file.text());if(importProject!==getProject())throw Error('El proyecto cambió. Vuelve a seleccionar el archivo en el proyecto correcto.');
  const result=await send('/import',data);await reload();status(result.inserted+' publicaciones nuevas; '+result.duplicates+' ya observadas. No se clasifican automáticamente.');
 }catch(e){status(e.message);}};
 byId('pulseClassification').ontoggle=async()=>{
  if(!byId('pulseClassification').open||!config?.can_import)return;
  try{const rows=await api(path()+'/documents');const list=byId('pulseReviewList');list.replaceChildren();
   for(const row of rows){const card=el('article',undefined,'dataset-item');card.append(el('b',row.title),el('small',config.actors.find(x=>x.id===row.actor_id)?.name||'Actor'));
    const tone=el('select');tone.setAttribute('aria-label','Tono de '+row.title);for(const [value,text] of [['','Sin clasificar'],['positive','Favorable'],['neutral','Neutral'],['negative','Desfavorable']]){const o=el('option',text);o.value=value;tone.append(o);}tone.value=row.sentiment||'';
    const emotion=el('select');emotion.setAttribute('aria-label','Emoción en '+row.title);for(const [value,text] of [['','Sin emoción'],...Object.entries(label).filter(([k])=>!['positive','neutral','negative'].includes(k))]){const o=el('option',text);o.value=value;emotion.append(o);}emotion.value=row.emotion||'';
    const button=el('button','Guardar revisión','outline');button.type='button';button.onclick=async()=>{button.disabled=true;try{const result=await send('/documents/'+row.id+'/actors/'+row.actor_id+'/classification',{sentiment:tone.value||null,emotion:emotion.value||null,expected_version:row.version},'PUT');row.version=result.version;await loadDashboard();status('Clasificación manual guardada.');}catch(e){status(e.message);}finally{button.disabled=false;}};
    card.append(tone,emotion,button);list.append(card);
   }
   if(!rows.length)list.append(el('p','Importa primero publicaciones normalizadas.','note'));
  }catch(e){status(e.message);}
 };
 document.querySelectorAll('[data-pulse-period]').forEach(b=>b.onclick=()=>{period=b.dataset.pulsePeriod;document.querySelectorAll('[data-pulse-period]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));byId('pulseCustom').hidden=period!=='custom';if(period!=='custom')loadDashboard().catch(e=>status(e.message));});
 byId('pulseRangeForm').onsubmit=event=>{event.preventDefault();loadDashboard().catch(e=>status(e.message));};
 byId('pulseNetwork').onchange=()=>loadDashboard().catch(e=>status(e.message));
 function resetProject(){configDirty=false;sequence++;config=null;actor=0;mode='real';period='24h';for(const id of ['pulseConfigForm','pulseImportForm'])byId(id).reset();byId('pulseNetwork').value='all';byId('pulseCustom').hidden=true;clear();byId('pulseReviewList').replaceChildren();byId('pulseConfigForm').hidden=true;byId('pulseImportForm').hidden=true;byId('pulseClassification').hidden=true;}
 async function focusActor(id){mode='real';actor=id;await reload();}
 return {canLeaveProject:()=>!configDirty||confirm('Hay cambios del proyecto sin guardar. ¿Descartarlos?'),reload,resetProject,focusActor};
}};
