/* Project-scoped account data quality. No remote fetches or identity scores. */
window.NexoAccountAudit={install({api,byId,getProject,onNavigate}){
 let generation=0,packet=null,diagnostics=[];
 const names={facebook:'Facebook',instagram:'Instagram',x:'X',tiktok:'TikTok',youtube:'YouTube',press:'Prensa',other:'Sitio público'};
 const states={ready:'Cortes alineados',no_captures:'Esperando primera captura',needs_review:'Revisar datos',paused:'En pausa',unregistered:'Falta registrar la cuenta'};
 const fields={followers:'Seguidores',posts:'Publicaciones',views:'Visualizaciones',impressions:'Impresiones',reach:'Alcance',interactions:'Interacciones'};
 const issues={future_capture:'Hay una captura con fecha futura.',invalid_payload:'Un registro tiene un formato que debe revisarse.',invalid_counter:'Hay campos numéricos inválidos.',no_counters:'Un registro no contiene cifras utilizables.',unknown_origin:'Falta identificar el origen de una captura.',invalid_period:'Falta un intervalo válido para la actividad.',invalid_reference:'Revisa las referencias de este actor.',duplicate_reference:'Hay una referencia repetida.',invalid_capture_reference:'Hay capturas cuya referencia necesita revisión.',unregistered_reference:'Registra esta cuenta en la ficha del actor.',reference_unreviewed:'La referencia está pendiente de revisión del equipo.',origin_mismatch:'Los cortes tienen orígenes distintos o sin identificar.',no_period_capture:'Falta una captura de actividad para el periodo elegido.',old_capture:'La última captura es anterior al periodo elegido.'};
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const date=x=>x?new Date(x).toLocaleString('es-MX',{dateStyle:'medium',timeStyle:'short'}):'—';
 function clear(){packet=null;diagnostics=[];byId('accountAuditContent').replaceChildren();byId('auditExport').disabled=true;byId('auditView').disabled=true;byId('auditSummary').textContent='';byId('auditVisible').textContent='';byId('auditCoverage').textContent='';byId('auditWindow').textContent='';
  for(const id of ['auditRegistered','auditCaptured','auditComparable','auditPending'])byId(id).textContent='—';}
 function draw(){if(!packet)return;const root=byId('accountAuditContent');root.replaceChildren();diagnostics=[];const visible=packet.items.filter(r=>byId('auditState').value==='all'||r.state===byId('auditState').value);
  for(const row of visible){const card=el('article',undefined,'panel audit-card');const head=el('div',undefined,'audit-card-head');
   const title=el('div');title.append(el('small',names[row.network]||'Sitio público','eyebrow'),el('h3',row.actor_name));head.append(title,el('span',states[row.state]||'Revisar datos','audit-state '+(row.state==='ready'?'audit-ready':'')));card.append(head);
   if(row.url){const link=el('a',row.url,'audit-url');try{const u=new URL(row.url);if(u.protocol==='https:'&&!u.username&&!u.password){link.href=u.href;link.target='_blank';link.rel='noopener noreferrer';}}catch{}card.append(link);}
   card.append(el('p',row.captures_checked+' registros revisados · última captura: '+date(row.latest_capture_at),'note'));
   if(row.state==='no_captures')card.append(el('p','Primera captura pendiente. Esta cuenta aún no tiene estadísticas guardadas.','audit-pending-copy'));
   const detail=el('div',undefined,'audit-diagnostic'),toggle=el('button','Ver diagnóstico','outline audit-toggle');
   detail.id='audit-diagnostic-'+generation+'-'+diagnostics.length;detail.hidden=true;toggle.type='button';toggle.setAttribute('aria-controls',detail.id);toggle.setAttribute('aria-expanded','false');
   toggle.onclick=()=>{detail.hidden=!detail.hidden;toggle.textContent=detail.hidden?'Ver diagnóstico':'Ocultar diagnóstico';toggle.setAttribute('aria-expanded',String(!detail.hidden));};
   diagnostics.push({detail,toggle});card.append(toggle);
   const grid=el('div',undefined,'audit-fields');for(const [key,label] of Object.entries(fields)){const value=row.fields[key],r=el('div',undefined,'network-metric-row');r.append(el('span',label),el('b',value==='available'?'Disponible':value==='invalid'?'Revisar':'Sin dato'));grid.append(r);}detail.append(el('p','Campos de la última captura, sin sumar cuentas ni periodos.','note'),grid);
   detail.append(el('p','Origen de la última captura: '+({manual:'Carga manual',apify_export:'Exportación Apify'}[row.latest_origin]||'Sin identificar'),'note'));
   detail.append(el('p','Actividad del corte: '+date(row.period_capture_at)+' · corte anterior: '+date(row.previous_capture_at),'note'));
   detail.append(el('p',row.comparable_fields.length?'Campos con periodos y origen alineados: '+row.comparable_fields.map(k=>fields[k]||k).join(', ')+'.':'Aún no hay campos con ambos cortes y el mismo origen.','note'));
   const list=el('ul');for(const code of row.issues){if(issues[code])list.append(el('li',issues[code]));}if(!row.issues.length)list.append(el('li','Sin incidencias en las comprobaciones del corte.'));detail.append(list);card.append(detail);
   const actions=el('div',undefined,'actions');for(const [text,page] of [['Ver Actores','actors'],['Ver Redes','networks'],['Ver Fidelidad','continuity']]){const b=el('button',text,'outline');b.type='button';b.onclick=()=>onNavigate(page);actions.append(b);}card.append(actions);root.append(card);
  }
  if(!visible.length)root.append(el('p',packet.items.length?'No hay cuentas con este estado en el corte.':'Agrega las cuentas públicas del proyecto en Actores.','note'));
  byId('auditVisible').textContent=visible.length+' de '+packet.items.length+' referencias en el corte';
 }
 function render(p){packet=p;const selected=byId('auditActor');selected.replaceChildren();const all=el('option','Todos los actores');all.value='0';selected.append(all);for(const actor of p.actors){const o=el('option',actor.name+(actor.active?'':' · en pausa'));o.value=String(actor.id);selected.append(o);}selected.value=String(p.selected_actor_id);
  for(const [id,key] of [['auditRegistered','registered'],['auditCaptured','with_captures'],['auditComparable','comparable'],['auditPending','pending']])byId(id).textContent=p.counts[key];
  byId('auditWindow').textContent='Actividad: '+date(p.window.start)+' a '+date(p.window.end)+' · corte anterior de igual duración';
  byId('auditCoverage').textContent=p.coverage_bounded?'Consulta acotada: hasta '+p.limits.actors+' actores, '+p.limits.captures_per_actor+' capturas y '+p.limits.accounts_per_actor+' cuentas por actor.':'Incluye las referencias registradas y las cuentas con capturas del proyecto; las cuentas en pausa se identifican por separado.';
  const waiting=p.items.filter(r=>r.state==='no_captures').length;
  byId('auditSummary').textContent=p.items.length+' referencias en este corte'+(waiting?' · '+waiting+' con primera captura pendiente.':'.');
  byId('auditView').disabled=!p.items.length;byId('auditExport').disabled=false;draw();
 }
 async function reload(){const pid=getProject(),token=++generation;clear();if(!pid)return;byId('auditStatus').textContent='Revisando referencias y capturas…';
  try{const end=new Date();end.setHours(0,0,0,0);const start=new Date(end);start.setDate(start.getDate()-Number(byId('auditPeriod').value||7));
   const q=new URLSearchParams({actor_id:byId('auditActor').value||0,network:byId('auditNetwork').value||'all',start:start.toISOString(),end:end.toISOString()});
   const p=await api('/api/projects/'+pid+'/account-audit?'+q);if(token!==generation||pid!==getProject())return;render(p);byId('auditStatus').textContent='';
  }catch(e){if(token===generation&&pid===getProject())byId('auditStatus').textContent=e.message;}
 }
 for(const id of ['auditActor','auditNetwork','auditPeriod'])byId(id).onchange=reload;
 byId('auditState').onchange=draw;byId('auditRefresh').onclick=reload;
 byId('auditView').onclick=()=>{if(!packet)return;if(!diagnostics.length){byId('auditState').value='all';draw();}for(const {detail,toggle} of diagnostics){detail.hidden=false;toggle.textContent='Ocultar diagnóstico';toggle.setAttribute('aria-expanded','true');}byId('accountAuditContent').scrollIntoView?.({behavior:'smooth',block:'start'});};
 byId('auditConfigure').onclick=()=>onNavigate('actors');
 byId('auditExport').onclick=()=>{if(!packet||packet.project_id!==getProject())return;const token=generation,pid=getProject();
  const value={...packet,visible_state:byId('auditState').value,items:packet.items.filter(r=>byId('auditState').value==='all'||r.state===byId('auditState').value)};
  const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'});if(token!==generation||pid!==getProject())return;const url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='Auditoria_cuentas_proyecto_'+pid+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 function resetProject(){generation++;clear();byId('auditActor').replaceChildren();byId('auditActor').value='0';byId('auditNetwork').value='all';byId('auditPeriod').value='7';byId('auditState').value='all';byId('auditStatus').textContent='';byId('auditVisible').textContent='';}
 return {reload,resetProject,canLeaveProject:()=>true};
}};
