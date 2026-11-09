/* Aggregate account continuity. No audience identities or external requests. */
window.NexoContinuity={install({api,byId,getProject,onConfigure}){
 const fidelity=window.NexoFidelity?.install({api,byId,getProject});
 let sequence=0,packet=null,actor=0,account='',measurement='',cut=null,dirty=false,busy=false;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const number=x=>x===null||x===undefined?'—':Number(x).toLocaleString('es-MX',{maximumFractionDigits:2});
 const date=x=>x?new Date(x).toLocaleString('es-MX',{dateStyle:'medium',timeStyle:'short'}):'—';
 const path=()=>'/api/projects/'+getProject()+'/continuity';
 function range(){if(cut)return cut;let end=new Date(),start;const period=byId('continuityPeriod').value;
  if(period==='custom'){if(!byId('continuityFrom').value||!byId('continuityTo').value)throw Error('Completa las fechas del periodo.');start=new Date(byId('continuityFrom').value+'T00:00:00');end=new Date(byId('continuityTo').value+'T00:00:00');end.setDate(end.getDate()+1);end=new Date(Math.min(end.getTime(),Date.now()));}
  else if(period==='1'){start=new Date(end.getTime()-86400000);}
  else{end.setHours(0,0,0,0);start=new Date(end);start.setDate(start.getDate()-Number(period));}return {start:start.toISOString(),end:end.toISOString()};}
 function clear(){fidelity?.invalidate();packet=null;for(const id of ['continuityParticipants','continuityReturning','continuityNew','continuityRetention','continuityRate'])byId(id).textContent='—';
  for(const id of ['continuityScope','continuityPeriodLabel','continuityDelta','continuitySource'])byId(id).textContent='';
  for(const id of ['continuitySeries','continuityComparison'])byId(id).replaceChildren();byId('continuityRing').style.background='#243354';byId('continuityExport').disabled=true;byId('continuityTemplate').disabled=true;byId('continuityImportPanel').hidden=true;}
 function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function render(p){packet=p;actor=p.selected_actor_id||0;account=p.selected_account?.url||'';measurement=p.selected_measurement;cut=p.window;
  for(const [id,rows,value] of [['continuityActor',p.actors.map(a=>({value:a.id,label:a.name+(a.kind==='primary'?' · principal':'')})),actor],
   ['continuityAccount',p.accounts.map(a=>({value:a.url,label:a.network+' · '+a.url})),account],
   ['continuityMeasurement',p.measurements.map(m=>({value:m,label:m})),measurement]]){const node=byId(id);node.replaceChildren();for(const row of rows){const option=el('option',row.label);option.value=row.value;node.append(option);}node.value=String(value);}
  byId('continuityScope').textContent=p.selected_account?p.selected_account.actor_name+' · '+p.selected_account.network:'Selecciona un actor con cuenta pública desde Actores.';
  byId('continuityPeriodLabel').textContent=date(p.window.start)+' a '+date(p.window.end);
  const c=p.current;for(const [id,value] of [['continuityParticipants',c.participants],['continuityReturning',c.returning],['continuityNew',c.new],['continuityRetention',c.retention_rate]])byId(id).textContent=number(value)+(id==='continuityRetention'&&value!==null?' %':'');
  byId('continuityRate').textContent=number(c.return_rate)+(c.return_rate!==null?' %':'');
  if(c.return_rate!==null)byId('continuityRing').style.background='conic-gradient(#47d5b4 '+Math.max(0,Math.min(100,c.return_rate))+'%,#243354 0)';
  byId('continuityDelta').textContent=p.return_rate_change_pp===null?'Comparación disponible con dos cortes equivalentes.':(p.return_rate_change_pp>0?'+':'')+number(p.return_rate_change_pp)+' puntos frente al periodo anterior';
  byId('continuitySource').textContent=c.status==='limited_sample'?'Corte reservado por tamaño de muestra.':c.status==='pending'?'El primer corte agregado de esta cuenta aparecerá aquí.':'Medición '+measurement+' · captura '+date(c.captured_at);
  if(c.reference)byId('continuitySource').textContent+=' · referencia: '+date(c.reference.start)+' a '+date(c.reference.end);
  const series=byId('continuitySeries');for(const point of p.series){const row=el('div',undefined,'continuity-series-row');row.append(el('small',date(point.start)+' a '+date(point.end)));const track=el('div',undefined,'continuity-track'),bar=el('span');bar.style.width=(point.return_rate===null?0:Math.max(0,Math.min(100,point.return_rate)))+'%';track.append(bar);row.append(track,el('b',number(point.return_rate)+(point.return_rate===null?'':' %')));series.append(row);}
  if(!p.series.length)series.append(el('p','Cada corte observado añadirá un punto a la evolución.','live-empty'));
  const table=el('table',undefined,'network-table'),head=el('tr');for(const label of ['Indicador','Este periodo','Periodo anterior'])head.append(el('th',label));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
  for(const [label,key,suffix] of [['Audiencia participante','participants',''],['Audiencia que regresa','returning',''],['Retorno sobre audiencia actual','return_rate',' %'],['Retención de audiencia anterior','retention_rate',' %']]){const tr=el('tr'),title=el('td',label);title.setAttribute('data-label','Indicador');tr.append(title);for(const [period,x] of [['Este periodo',p.current],['Periodo anterior',p.previous]]){const cell=el('td',number(x[key])+(x[key]===null?'':suffix));cell.setAttribute('data-label',period);tr.append(cell);}body.append(tr);}table.append(body);byId('continuityComparison').append(table);
  if(!p.baseline_consistent)byId('continuityComparison').append(el('p','Las bases declaradas difieren: la variación queda pendiente de conciliación.','note'));
  if(p.coverage_bounded)byId('continuityComparison').append(el('p','Consulta limitada a las últimas '+p.query_limit+' capturas.','note'));
  fidelity?.reload(p);
  byId('continuityImportPanel').hidden=!p.can_import;byId('continuityExport').disabled=false;byId('continuityTemplate').disabled=!p.can_import||!p.selected_account;
 }
 async function reload(){if(!getProject())return;const stamp=++sequence,pid=getProject();clear();byId('continuityStatus').textContent='Preparando la continuidad de audiencia…';
  try{const r=range(),p=await api(path()+'?'+new URLSearchParams({...r,actor_id:actor,network:byId('continuityNetwork').value,account_url:account,measurement}));if(stamp!==sequence||pid!==getProject())return;byId('continuityStatus').textContent='';render(p);}
  catch(e){if(stamp===sequence&&pid===getProject())byId('continuityStatus').textContent=e.message;}}
 byId('continuityActor').onchange=()=>{actor=Number(byId('continuityActor').value);account=measurement='';reload();};
 byId('continuityNetwork').onchange=()=>{account=measurement='';reload();};byId('continuityAccount').onchange=()=>{account=byId('continuityAccount').value;measurement='';reload();};
 byId('continuityMeasurement').onchange=()=>{measurement=byId('continuityMeasurement').value;reload();};
 byId('continuityPeriod').onchange=()=>{cut=null;measurement='';byId('continuityDates').hidden=byId('continuityPeriod').value!=='custom';if(byId('continuityPeriod').value!=='custom')reload();else{sequence++;clear();}};
 for(const id of ['continuityFrom','continuityTo'])byId(id).onchange=()=>{sequence++;cut=null;measurement='';clear();};
 byId('continuityRefresh').onclick=()=>{cut=null;reload();};byId('continuityConfigure').onclick=()=>onConfigure();
 byId('continuityExport').onclick=()=>{if(packet)download(packet,'NEXO_Continuidad_Corte.json');};
 byId('continuityTemplate').onclick=()=>{if(!packet?.can_import||!packet.selected_account)return;const a=packet.selected_account,w=packet.window,duration=new Date(w.end)-new Date(w.start);
  download({provider:'manual',items:[{actor_id:a.actor_id,network:a.network,url:a.url,measurement_id:'source-participation-v1',contract_version:'participating-accounts-v1',
   period_from:w.start,period_to:w.end,reference_from:new Date(new Date(w.start)-duration).toISOString(),reference_to:w.start,captured_at:new Date().toISOString(),participants:null,returning:null,reference_participants:null}]},'NEXO_Continuidad_Plantilla.json');};
 byId('continuityFile').onchange=()=>{dirty=!!byId('continuityFile').files.length;};
 byId('continuityImportForm').onsubmit=async e=>{e.preventDefault();if(busy||!packet?.can_import)return;const file=byId('continuityFile').files[0];if(!file)return;if(file.size>1_000_000){byId('continuityImportStatus').textContent='Máximo 1 MB por archivo.';return;}
  const pid=getProject(),stamp=sequence;busy=true;byId('continuityImport').disabled=true;
  try{const body=JSON.parse(await file.text());if(pid!==getProject()||stamp!==sequence)return;const result=await api(path()+'/captures',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(pid!==getProject())return;dirty=false;byId('continuityFile').value='';await reload();byId('continuityImportStatus').textContent=result.inserted+' cortes incorporados · '+result.duplicates+' ya existentes.';}
  catch(e){if(pid===getProject())byId('continuityImportStatus').textContent=e instanceof SyntaxError?'El archivo no es un JSON válido.':e.message==='Error de consulta 422'?'Revisa cuentas, fechas y conteos agregados del archivo.':e.message;}
  finally{busy=false;byId('continuityImport').disabled=false;}};
 function resetProject(){fidelity?.reset();sequence++;actor=0;account=measurement='';cut=null;dirty=false;clear();for(const id of ['continuityActor','continuityAccount','continuityMeasurement'])byId(id).replaceChildren();byId('continuityNetwork').value='all';byId('continuityPeriod').value='7';byId('continuityDates').hidden=true;
  for(const id of ['continuityFrom','continuityTo','continuityFile'])byId(id).value='';byId('continuityImportPanel').open=false;byId('continuityStatus').textContent='';byId('continuityImportStatus').textContent='';}
 return {focusActor:id=>{actor=Number(id)||0;account=measurement='';cut=null;byId('continuityNetwork').value='all';byId('continuityPeriod').value='7';byId('continuityDates').hidden=true;return reload();},reload,resetProject,canLeaveProject:()=>!busy&&(fidelity?.canLeaveProject()??true)&&(!dirty||confirm('Hay un archivo sin incorporar. ¿Descartarlo al cambiar de proyecto?'))};
}};
