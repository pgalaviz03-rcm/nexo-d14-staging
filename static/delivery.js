/* Own-user schedules and local previews. No channel SDKs or provider requests. */
window.NexoDelivery={install({api,byId,getProject,getCut,onAssessmentSaved,canConfigure=()=>true}){
 let version=0,sequence=0,cutSequence=0,dirty=false;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const base=()=>'/api/projects/'+getProject()+'/briefing';
 const send=(path,body,method='POST')=>api(base()+path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const message=t=>{byId('deliveryStatus').textContent=t;};
 const states={waiting_review:'Falta un briefing habilitado y vigente para ese periodo',blocked_provider:'Proveedor desconectado; destino pendiente de verificar',blocked_recipient:'Falta un destino autorizado',cancelled:'Cancelada por cambio de configuración'};
 function cutChanged(p){cutSequence++;byId('deliveryPreviewText').textContent='';byId('assessmentList').replaceChildren();byId('assessmentPanel').hidden=!p?.can_save;byId('assessmentPanel').open=false;
  byId('briefingAnalysisState').textContent='';if(p?.can_save&&canConfigure())analysisState(p,cutSequence);
 }
 async function analysisState(cut,cutStamp){const pid=getProject(),stamp=sequence,query=new URLSearchParams({start:cut.filters.start,end:cut.filters.end});
  const current=()=>pid===getProject()&&stamp===sequence&&cutStamp===cutSequence;
  try{if(cut.can_save)await send('/analysis/prepare',{start:cut.filters.start,end:cut.filters.end});
   if(!current())return;const r=await api(base()+'/analysis?'+query);if(!current())return;
   const c=r.counts,parts=[];if(c.completed)parts.push(c.completed+' piezas con análisis de IA');const pending=(c.queued||0)+(c.processing||0)+(c.unqueued||0);if(pending)parts.push(pending+' pendientes de análisis');
   if(c.needs_review||c.failed)parts.push((c.needs_review+c.failed)+' por revisar');
   byId('briefingAnalysisState').textContent=parts.join(' · ')||'Sin piezas pendientes en este corte.';
  }catch(e){if(current())byId('briefingAnalysisState').textContent='No se pudo actualizar el estado del análisis. Intenta actualizar el corte.';}
 }
 async function reload(){if(!getProject()||!canConfigure())return;const pid=getProject(),stamp=++sequence;
  try{const r=await api(base()+'/delivery');if(stamp!==sequence||pid!==getProject())return;const s=r.settings;if(!dirty)version=s.version;
   if(!dirty){for(const [id,key] of [['deliveryChannel','channel'],['deliveryFrequency','frequency'],['deliveryTime','local_time'],['deliveryTimezone','timezone'],['deliveryWeekday','weekday'],['deliveryLookback','lookback_days']])byId(id).value=String(s[key]);byId('deliveryEnabled').checked=s.enabled;}
   byId('deliveryDestination').placeholder=s.destination_masked?'Guardado: '+s.destination_masked+' · vacío conserva el destino':'Correo o ID numérico privado de Telegram';
   byId('deliveryNext').textContent=s.next_scheduled_for?'Próximo horario previsto: '+new Intl.DateTimeFormat('es-MX',{timeZone:s.timezone,dateStyle:'full',timeStyle:'short'}).format(new Date(s.next_scheduled_for))+' · '+s.timezone:'Programación pausada.';
   byId('deliveryWeekdayLabel').hidden=byId('deliveryFrequency').value!=='weekly';byId('deliverySimulate').disabled=!s.enabled;
   const list=byId('deliveryJobs');list.replaceChildren();for(const job of r.jobs)list.append(el('p','SIMULACIÓN · '+(states[job.state]||job.state)+' · '+new Date(job.scheduled_for).toLocaleString('es-MX'),'note'));
   if(!r.jobs.length)list.append(el('p','Sin simulaciones registradas.','note'));
   if(s.destination_problem)message('Reconfigura el destino: su clave de cifrado cambió.');
  }catch(e){if(stamp===sequence)message(e.message);}
 }
 byId('deliveryFrequency').onchange=()=>{byId('deliveryWeekdayLabel').hidden=byId('deliveryFrequency').value!=='weekly';};
 byId('deliveryForm').addEventListener('input',()=>{dirty=true;});
 byId('deliveryForm').onsubmit=async e=>{e.preventDefault();const button=byId('deliverySave');button.disabled=true;
  try{await send('/delivery',{channel:byId('deliveryChannel').value,frequency:byId('deliveryFrequency').value,local_time:byId('deliveryTime').value,
   timezone:byId('deliveryTimezone').value,weekday:Number(byId('deliveryWeekday').value),lookback_days:Number(byId('deliveryLookback').value),enabled:byId('deliveryEnabled').checked,
   destination:byId('deliveryDestination').value||null,authorized_destination:byId('deliveryConsent').checked,clear_destination:byId('deliveryClear').checked,expected_version:version},'PUT');
   dirty=false;byId('deliveryDestination').value='';byId('deliveryConsent').checked=false;byId('deliveryClear').checked=false;await reload();message('Preferencia privada guardada.');
  }catch(e){message(e.message);}finally{button.disabled=false;}
 };
 byId('deliveryPreview').onclick=async()=>{try{const cut=getCut();if(!cut)throw Error('Actualiza primero el corte de Briefing.');const pid=getProject(),stamp=sequence,cutStamp=cutSequence;
  const p=await send('/delivery/preview',{start:cut.filters.start,end:cut.filters.end});if(pid===getProject()&&stamp===sequence&&cutStamp===cutSequence)byId('deliveryPreviewText').textContent=p.text;
 }catch(e){message(e.message);}};
 byId('deliverySimulate').onclick=async()=>{try{const r=await api(base()+'/delivery/simulate',{method:'POST'});await reload();message('Simulación local: '+states[r.state]+'. Ningún mensaje enviado.');}catch(e){message(e.message);}};
 async function assessments(){const cut=getCut();if(!cut||!cut.can_save)return;const pid=getProject(),stamp=sequence,cutStamp=cutSequence;
  try{const q=new URLSearchParams({start:cut.filters.start,end:cut.filters.end,source_kind:byId('assessmentKind').value});const r=await api(base()+'/assessments?'+q);
   if(pid!==getProject()||stamp!==sequence||cutStamp!==cutSequence)return;const list=byId('assessmentList');list.replaceChildren();
   for(const row of r.items){const card=el('article',undefined,'dataset-item');card.append(el('b',row.title),el('p',row.excerpt,'note'));
    card.append(el('p',row.origin==='ai'?'Análisis de IA':row.origin==='correction'?'Corrección editorial':'Pendiente de análisis','note'));
    if(row.stale)card.append(el('p','La fuente cambió; revisa las etiquetas otra vez.','note'));
    const select=(label,options,value)=>{const box=el('label',label),input=el('select');for(const [v,t] of options){const o=el('option',t);o.value=v;input.append(o);}input.value=value??'';box.append(input);card.append(box);return input;};
    const tone=select('Tono ',[['','Sin clasificar'],['positive','Positivo'],['neutral','Neutral'],['negative','Negativo']],row.sentiment);
    const emotion=select('Emoción ',[['','Sin clasificar'],['joy','Alegría'],['anger','Ira'],['surprise','Sorpresa'],['fear','Miedo'],['sadness','Tristeza']],row.emotion);
    const mockery=select('Burla ',[['','Sin revisar'],['yes','Sí'],['no','No']],row.mockery===null?'':row.mockery?'yes':'no');
    const button=el('button','Guardar corrección','outline');button.type='button';button.onclick=async()=>{button.disabled=true;try{
     await send('/assessments/'+row.kind+'/'+row.id,{sentiment:tone.value||null,emotion:emotion.value||null,mockery:mockery.value===''?null:mockery.value==='yes',expected_version:row.expected_version,source_sha256:row.source_sha256},'PUT');
     await onAssessmentSaved();message('Corrección guardada. El corte incorpora las etiquetas vigentes.');
    }catch(e){message(e.message);}finally{button.disabled=false;}};card.append(button);list.append(card);
   }
   if(!r.items.length)list.append(el('p','Sin piezas en este corte.','note'));if(r.truncated)list.append(el('p','Lista acotada a 100 registros. Filtra por tipo para revisar otras piezas.','note'));
  }catch(e){message(e.message);}
 }
 byId('assessmentPanel').ontoggle=()=>{if(byId('assessmentPanel').open)assessments();};byId('assessmentKind').onchange=assessments;
 function resetProject(){sequence++;version=0;dirty=false;byId('deliveryForm').reset();byId('deliveryDestination').value='';byId('deliveryDestination').placeholder='Correo o ID numérico privado de Telegram';byId('deliverySimulate').disabled=true;byId('assessmentKind').value='all';byId('deliveryPreviewText').textContent='';byId('deliveryJobs').replaceChildren();byId('deliveryNext').textContent='';message('');cutChanged(null);}
 return {reload,resetProject,cutChanged,canLeaveProject:()=>!dirty||confirm('Hay una programación sin guardar. ¿Descartarla al cambiar de proyecto?')};
}};
