/* Evidence-first local briefing. Provider calls and automatic publication absent. */
window.NexoBriefing={install({api,byId,getProject,onSaved,onCutChanged}){
 let packet=null,sequence=0,dirty=false,loading=false,saveAllowed=false;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const fmt=x=>x===null||x===undefined?'—':Number(x).toLocaleString('es-MX',{maximumFractionDigits:1});
 const message=t=>{byId('briefingStatus').textContent=t;};
 function clear(){packet=null;byId('briefingAnalytics').replaceChildren();onCutChanged?.(null);for(const id of ['briefingNewsCount','briefingReviewed','briefingMentions','briefingAlerts'])byId(id).textContent='—';
  for(const id of ['briefingNews','briefingSignals','briefingTopics','briefingSources','briefingPending'])byId(id).replaceChildren();
  byId('briefingLead').textContent='Preparando la lectura del archivo de este proyecto.';byId('briefingStamp').textContent='';
  byId('briefingExport').disabled=true;byId('briefingSave').disabled=true;byId('briefingSavePanel').hidden=true;}
 function dates(){const now=new Date();if(byId('briefingPeriod').value==='custom'){
   const a=byId('briefingStart').value,b=byId('briefingEnd').value;if(!a||!b)throw Error('Completa las fechas del periodo.');
   const start=new Date(a+'T00:00:00'),end=new Date(b+'T00:00:00');end.setDate(end.getDate()+1);
   return {start:start.toISOString(),end:new Date(Math.min(end.getTime(),now.getTime())).toISOString()};
  }return {start:new Date(now.getTime()-Number(byId('briefingPeriod').value)*86400000).toISOString(),end:now.toISOString()};}
 function link(title,url){const a=el('a',title);if(/^https:\/\//i.test(url||'')){a.href=url;a.target='_blank';a.rel='noopener noreferrer';}return a;}
 function render(p){
  packet=p;saveAllowed=p.can_save;byId('briefingNewsCount').textContent=fmt(p.news_count);byId('briefingReviewed').textContent=fmt(p.review_status.reviewed)+' / '+fmt(p.news_count);
  const analytics=byId('briefingAnalytics');analytics.replaceChildren();
  if(p.content_analytics){const a=p.content_analytics;
   analytics.append(el('h3',fmt(a.pieces)+' piezas únicas observadas · '+a.mood),el('p','Índice de tono: '+fmt(a.mood_index)+' /100 · '+a.tone_classified+' piezas clasificadas de '+a.pieces+'. Mínimo: '+a.minimum_classified+'.','note'));
   for(const row of a.tone)analytics.append(el('p',({positive:'Positivo',negative:'Negativo',neutral:'Neutral'}[row.label])+': '+fmt(row.percentage)+' % · '+row.count+' piezas'));
   const emotions={joy:'Alegría',anger:'Ira',surprise:'Sorpresa',fear:'Miedo',sadness:'Tristeza'};
   analytics.append(el('h3','Emociones del contenido'));
   for(const row of a.emotions)analytics.append(el('p',emotions[row.emotion]+': '+fmt(row.percentage)+' % · '+row.count+' piezas'));
   analytics.append(el('p','Base de emociones: '+a.emotion_classified+' piezas. Burla: '+fmt(a.mockery_percentage)+' % · '+a.mockery_classified+' piezas codificadas.','note'),el('p',a.methodology,'note'));
  }else analytics.append(el('p','Sin desglose de piezas en este corte.','note'));
  byId('briefingMentions').textContent=fmt(p.pulse.metrics.mentions);byId('briefingAlerts').textContent=fmt(p.pulse.active_alerts);
  byId('briefingLead').textContent=p.news_count||p.pulse.metrics.mentions?fmt(p.news_count)+' publicaciones periodísticas y '+fmt(p.pulse.metrics.mentions)+' menciones de actores en contenido público. Revisa las fuentes y lo que sigue pendiente.':'Este corte todavía no tiene publicaciones. Puedes ampliar el periodo o incorporar fuentes autorizadas.';
  byId('briefingStamp').textContent=p.project_name+' · '+new Date(p.filters.start).toLocaleString('es-MX')+' → '+new Date(p.filters.end).toLocaleString('es-MX');
  const news=byId('briefingNews');news.replaceChildren();
  for(const n of p.news){const row=el('article',undefined,'brief-story');row.append(el('small','['+n.citation+'] '+n.source+' · '+new Date(n.at).toLocaleString('es-MX'),'note'),link(n.title,n.url));
   if(n.excerpt)row.append(el('p',n.excerpt));
   row.append(el('span',n.review_status==='reviewed'?'Revisión registrada':n.review_status==='needs_check'?'Requiere comprobación':'Sin revisar','brief-label'));
   if(n.date_basis==='ingestion')row.append(el('small','Sin fecha de publicación; el corte usa fecha de ingreso.','note'));news.append(row);
  }
  if(!p.news.length)news.append(el('p','Sin notas periodísticas para este periodo.','hint'));
  byId('briefingNewsLimit').textContent=p.coverage.news_truncated?'Se muestran las 8 notas más recientes de '+fmt(p.news_count)+'. El orden usa fecha; no mide alcance.':'Orden por fecha; no mide alcance ni verifica afirmaciones.';
  const signals=byId('briefingSignals');signals.replaceChildren();const m=p.pulse.metrics;
  signals.append(el('h3','Señales de Pulso'),el('p',fmt(m.classified)+' de '+fmt(m.mentions)+' menciones clasificadas. Mínimo: '+p.pulse.minimum_classified+'.','note'));
  signals.append(el('p',m.score_delta===null?'Sin línea base suficiente para comparar.':(m.score_delta>0?'+':'')+fmt(m.score_delta)+' puntos frente a los 90 días previos.','note'));
  for(const a of p.pulse.alerts)signals.append(el('p',a.name+' · '+fmt(a.value)+' / umbral '+fmt(a.threshold),'pulse-alert'));
  if(p.pulse.active_alerts===null)signals.append(el('p','Alertas sin evaluación suficiente; no equivale a cero riesgo.','note'));
  for(const n of p.pulse.sources){const row=el('p');row.append(link('['+n.citation+'] '+n.title,n.url));signals.append(row);}
  signals.append(el('p','Tono del contenido observado; no es una encuesta del electorado.','note'));
  const topics=byId('briefingTopics');topics.replaceChildren();for(const t of p.topics)topics.append(el('p',t.name+' · '+fmt(t.count)+' publicaciones'+(t.active?'':' · tema archivado')));
  if(!p.topics.length)topics.append(el('p','Todavía no hay temas asignados a las notas de este corte.','note'));
  const sources=byId('briefingSources');sources.replaceChildren();for(const s of p.sources)sources.append(el('p',s.name+' · '+fmt(s.count),'note'));
  if(!p.sources.length)sources.append(el('p','Sin fuentes periodísticas en el corte.','note'));
  const pending=byId('briefingPending');pending.replaceChildren();
  for(const text of [fmt(p.review_status.unreviewed)+' notas sin revisar.',fmt(p.review_status.needs_check)+' notas marcadas para comprobación.',fmt(p.news_without_publication_date)+' notas sin fecha de publicación.',fmt(p.documents_in_archive)+' archivos en biblioteca, sin filtro de periodo; no incluidos automáticamente en este corte.'])pending.append(el('li',text));
  if(p.coverage.bounded)pending.append(el('li','Las listas de fuentes, notas, temas o alertas pueden estar acotadas; los conteos mantienen su universo declarado.'));
  byId('briefingExport').disabled=false;byId('briefingSavePanel').hidden=!saveAllowed;byId('briefingSave').disabled=!saveAllowed||!p.citations.length;
  if(!byId('briefingTitle').value)byId('briefingTitle').value='Briefing · '+p.project_name.slice(0,90)+' · '+new Date(p.filters.end).toLocaleDateString('es-MX');
  message('Corte local actualizado · IA y conexiones externas apagadas.');
  onCutChanged?.(p);
 }
 async function reload(){if(!getProject())return;const project=getProject(),token=++sequence;loading=true;clear();message('Consultando las fuentes del proyecto…');
  try{const q=new URLSearchParams(dates());const result=await api('/api/projects/'+project+'/briefing?'+q);if(token===sequence&&project===getProject())render(result);}
  catch(e){if(token===sequence)message(e.message);}finally{if(token===sequence)loading=false;}
 }
 byId('briefingRefresh').onclick=()=>reload();
 byId('briefingPeriod').onchange=()=>{byId('briefingCustom').hidden=byId('briefingPeriod').value!=='custom';if(byId('briefingPeriod').value!=='custom')reload();else{sequence++;clear();message('Selecciona el periodo y pulsa Actualizar corte.');}};
 byId('briefingStart').onchange=byId('briefingEnd').onchange=()=>{sequence++;clear();message('Las fechas cambiaron. Actualiza el corte antes de guardar.');};
 byId('briefingSaveForm').addEventListener('input',()=>{dirty=true;});
 byId('briefingSaveForm').onsubmit=async e=>{e.preventDefault();if(!packet||!saveAllowed||loading)return;
  const project=getProject(),selected=packet;byId('briefingSave').disabled=true;
  try{const result=await api('/api/projects/'+project+'/briefing/reports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
   start:selected.filters.start,end:selected.filters.end,preview_sha256:selected.preview_sha256,title:byId('briefingTitle').value,note:byId('briefingNote').value})});
   if(project!==getProject())return;dirty=false;message('Corte guardado como borrador. Habilítalo para lectores desde Reportes tras revisarlo.');await onSaved(result.id);
  }catch(e){if(project===getProject())message(e.message);}finally{if(project===getProject())byId('briefingSave').disabled=!packet||!packet.citations.length;}
 };
 byId('briefingExport').onclick=()=>{if(!packet)return;const blob=new Blob([JSON.stringify({...packet,editorial_note:byId('briefingNote').value},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='Briefing_Proyecto_'+getProject()+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 function resetProject(){sequence++;dirty=false;saveAllowed=false;loading=false;byId('briefingSaveForm').reset();byId('briefingPeriod').value='7';byId('briefingCustom').hidden=true;clear();message('');}
 return {reload,resetProject,getCut:()=>packet,canLeaveProject:()=>!dirty||confirm('Hay una nota de Briefing sin guardar. ¿Quieres descartarla al cambiar de proyecto?')};
}};
