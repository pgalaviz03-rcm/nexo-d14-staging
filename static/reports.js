/* Project reports: frozen evidence, explicit release, and guarded asynchronous work. */
window.NexoReports={install({api,byId,page,getProject}){
 let documentId=null,selected=null,canWrite=false,canPublish=false,listSequence=0,openSequence=0,generation=0,dirty=false,busy=false,archive=[];
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const prefix=()=>'/api/projects/'+getProject()+'/reports';
 const message=t=>{byId('reportMessage').textContent=t;};
 const current=(pid,gen)=>pid===getProject()&&gen===generation;
 const safeToLeave=()=>!busy&&(!dirty||confirm('Hay cambios sin guardar en este informe. ¿Quieres descartarlos?'));
 const kind=s=>s?.mode==='local_documentary_briefing_v1'?'briefing':s?.mode==='explorer_selection_v1'?'selection':'documentary';
 const labels={briefing:'Briefing',selection:'Selección de evidencias',documentary:'Informe documental'},states={draft:'Borrador',released:'Habilitado para lectores',updated:'Actualización sin habilitar'};
 const stamp=x=>x?new Date(x).toLocaleString('es-MX',{dateStyle:'medium',timeStyle:'short'}):'Sin fecha';
 const normalize=x=>String(x).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 function controls(){const historical=!!selected&&selected.version!==selected.current_version,frozen=!!selected&&kind(selected.snapshot)!=='documentary';
  byId('reportForm').hidden=!canWrite||frozen;byId('reportNew').hidden=!canWrite;byId('reportNew').disabled=busy;
  for(const id of ['reportTitle','reportQuestion','reportNote','reportKind'])byId(id).disabled=busy||historical||!canWrite;
  byId('reportDocumentScope').hidden=false;byId('reportDocumentScope').textContent=documentId?'La búsqueda de este informe se limita al documento elegido en Biblioteca.':'Fuentes: '+({'all':'noticias y documentos del proyecto','news':'noticias del proyecto','documents':'documentos del proyecto'}[byId('reportKind').value]||'archivo del proyecto')+'.';
  byId('reportClearScope').hidden=!documentId;byId('reportClearScope').disabled=busy||historical||!canWrite;
  if(documentId){byId('reportKind').value='documents';byId('reportKind').disabled=true;}
  byId('reportSave').disabled=busy||!canWrite||historical||frozen;byId('reportSave').textContent=selected?'Guardar nueva versión':'Guardar borrador';
  byId('reportPublish').hidden=!selected||!canPublish||historical||selected.version===selected.published_version;byId('reportPublish').disabled=busy||dirty;
  for(const id of ['reportExport','reportDocument','reportVersions','reportOrigin']){byId(id).hidden=!selected;byId(id).disabled=busy;}
  byId('reportFormHeading').textContent=selected?(frozen?'Informe con fuentes conservadas':'Continuar el informe'):'Nuevo informe con fuentes';
 }
 function clear(){documentId=null;selected=null;dirty=false;openSequence++;byId('reportForm').reset();byId('reportBody').replaceChildren();byId('reportVersionList').replaceChildren();byId('reportSelectedTitle').textContent='Selecciona un informe o prepara el primero.';controls();}
 function show(report){selected=report;dirty=false;const snap=report.snapshot;documentId=snap.filters.document_id||null;byId('reportSelectedTitle').textContent=snap.title;
  byId('reportTitle').value=snap.title;byId('reportQuestion').value=snap.context.question;byId('reportNote').value=snap.editorial_note;byId('reportKind').value=snap.filters.source_kind;
  const box=byId('reportBody');box.replaceChildren();const header=el('div',undefined,'report-version-header');header.append(el('span',labels[kind(snap)],'pill'),el('b','Versión '+report.version),el('span',stamp(report.created_at),'note'));box.append(header);
  const released=report.is_released??(report.published_version===report.version);box.append(el('p',released?'Habilitada para lectores del proyecto.':'Borrador de trabajo.','note'));
  if(report.published_version&&report.published_version!==report.version)box.append(el('p','Lectura por defecto del proyecto: versión '+report.published_version+'.','note'));
  if(report.version!==report.current_version)box.append(el('p','Versión histórica de solo lectura. Abre la versión actual desde el archivo para continuar.','note'));
  if(kind(snap)==='briefing'){const cut=snap.briefing,n=v=>v===null||v===undefined?'—':String(v);box.append(el('h3','Corte documental de Briefing'),el('p',stamp(cut.filters.start)+' → '+stamp(cut.filters.end),'note'),el('p',cut.news_count+' notas · '+cut.pulse.metrics.mentions+' menciones · '+n(cut.pulse.active_alerts)+' señales activadas'));
   const a=cut.content_analytics;if(a){box.append(el('p',n(a.pieces)+' piezas del corpus · '+n(a.tone_classified)+' con tono clasificado · índice '+n(a.mood_index)+'/100 · burla '+n(a.mockery_percentage)+' %'));const names={positive:'Positivo',neutral:'Neutral',negative:'Negativo',joy:'Alegría',anger:'Ira',fear:'Miedo',sadness:'Tristeza',surprise:'Sorpresa'};
    for(const r of a.tone||[])box.append(el('p',(names[r.label]||r.label)+': '+n(r.percentage)+' %','note'));for(const r of a.emotions||[])box.append(el('p',(names[r.emotion]||r.emotion)+': '+n(r.percentage)+' %','note'));}
   if(cut.topics?.length){box.append(el('h3','Temas consignados en el corte'));for(const t of cut.topics)box.append(el('p',t.name+' · '+t.count+' notas'));}
   for(const r of cut.pulse.alerts||[])box.append(el('p',r.name+' · '+n(r.value)+' / '+n(r.threshold),'note'));
  }
  if(kind(snap)!=='documentary')box.append(el('p','Fuentes conservadas al guardar. Prepara otro corte o selección desde su origen para incorporar cambios.','note'));
  if(snap.editorial_note){box.append(el('h3','Nota del equipo'));const note=el('p',snap.editorial_note);note.style.whiteSpace='pre-wrap';box.append(note);}
  box.append(el('p',snap.scope,'note'));if(snap.context.coverage.bounded)box.append(el('p','Las fuentes se recuperaron dentro del límite de consulta de ese corte.','note'));
  for(const cite of snap.context.citations){const card=el('details',undefined,'report-citation'),summary=el('summary','['+cite.citation+'] '+cite.title);card.append(summary,el('p',cite.source,'note'));
   if(cite.published_at)card.append(el('small',({'uploaded':'Carga del archivo','ingested':'Ingreso al archivo'}[cite.date_basis]||'Fecha consignada')+': '+stamp(cite.published_at)));
   const text=el('p',cite.excerpt);text.style.whiteSpace='pre-wrap';card.append(text);if(/^https:\/\//i.test(cite.url||'')){const link=el('a','Consultar fuente original ↗');link.href=cite.url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}box.append(card);}
  const provenance=el('details');provenance.append(el('summary','Integridad y procedencia'),el('p','Huella de la versión: '+report.sha256,'dataset-hash'),el('p','La copia conserva sus fragmentos. La huella detecta cambios; no certifica la veracidad de las fuentes.','note'));box.append(provenance);
  byId('reportVersionList').replaceChildren();controls();
 }
 async function loadReport(id,version){const token=++openSequence,pid=getProject(),gen=generation;message('Abriendo informe…');try{const result=await api(prefix()+'/'+id+(version?'/versions/'+version:''));if(!current(pid,gen)||token!==openSequence)return false;show(result);message('Informe recuperado del archivo local.');return true;}catch(e){if(current(pid,gen)&&token===openSequence)throw e;return false;}}
 async function open(id,version){if(!safeToLeave())return false;return loadReport(id,version);}
 function renderList(){const q=normalize(byId('reportSearch').value),filter=byId('reportStateFilter').value,type=byId('reportTypeFilter').value;
  const list=byId('reportList');list.replaceChildren();const rows=archive.filter(r=>normalize(r.title).includes(q)&&(filter==='all'||r.state===filter)&&(type==='all'||r.origin===type));
  for(const report of rows){const row=el('article',undefined,'report-library-card');row.append(el('span',labels[report.origin]||labels.documentary,'eyebrow'),el('h4',report.title),el('span',states[report.state],'report-state '+report.state),el('p','Versión '+report.version+' · '+report.citations+' fuentes · '+stamp(report.created_at),'note'));
   if(report.published_version&&report.published_version!==report.version)row.append(el('small','Los lectores consultan la versión '+report.published_version+'.'));
   const button=el('button','Abrir informe','outline');button.type='button';button.disabled=busy;button.onclick=()=>open(report.id).catch(e=>message(e.message));row.append(button);list.append(row);}
  if(!rows.length)list.append(el('p',archive.length?'No hay informes que coincidan con estos filtros.':canWrite?'Prepara tu primer informe desde Briefing, Explorador o una búsqueda documental.':'Todavía no hay informes habilitados para lectura.','live-empty'));
  byId('reportFilteredCount').textContent=rows.length+' de '+archive.length+' informes del archivo consultado';
  for(const [id,value] of [['reportCount',archive.length],['reportDraftCount',archive.filter(r=>r.state==='draft').length],['reportReleasedCount',archive.filter(r=>r.state==='released').length],['reportUpdatedCount',archive.filter(r=>r.state==='updated').length]])byId(id).textContent=String(value);
 }
 async function reload(){if(!getProject())return;const token=++listSequence,pid=getProject(),gen=generation,result=await api(prefix());if(!current(pid,gen)||token!==listSequence)return;
  const lostWrite=canWrite&&!result.can_write;canWrite=result.can_write;canPublish=result.can_publish;if(lostWrite){openSequence++;if(selected&&!(selected.is_released??(selected.version===selected.published_version)))clear();}archive=result.items.map(r=>({...r,origin:r.origin||'documentary',state:r.state||(!r.published_version?'draft':r.version===r.published_version?'released':'updated')}));renderList();
  byId('reportListNote').textContent=result.truncated?'Archivo consultado: los 100 informes más recientes autorizados.':'Archivo de informes autorizados del proyecto.';byId('summaryReports').textContent=result.published_count;
  byId('summaryNext').textContent=canWrite?'Revisa las publicaciones y prepara un informe con fuentes.':'Consulta los informes habilitados y el contexto del territorio.';byId('summaryPrepare').hidden=!canWrite;
  for(const id of ['addRssFeed','rssCsvImport','uploadDataset'])byId(id).hidden=!canWrite;controls();return result;
 }
 byId('reportNew').onclick=()=>{if(safeToLeave()){clear();message('Completa el título y el tema. Las fuentes se recuperan al guardar.');}};
 byId('reportClearScope').onclick=()=>{if(busy||!canWrite)return;documentId=null;dirty=true;controls();};
 byId('reportForm').addEventListener('input',()=>{if(!busy)dirty=true;controls();});
 byId('reportForm').addEventListener('submit',async event=>{event.preventDefault();if(busy||!canWrite||(selected&&(selected.version!==selected.current_version||kind(selected.snapshot)!=='documentary')))return;
  const pid=getProject(),gen=generation,id=selected?.id,body={title:byId('reportTitle').value,question:byId('reportQuestion').value,note:byId('reportNote').value,source_kind:byId('reportKind').value,document_id:documentId,limit:5};if(selected)body.expected_version=selected.version;
  busy=true;controls();message('Guardando una copia de las fuentes…');try{const result=await api(prefix()+(id?'/'+id+'/versions':''),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!current(pid,gen))return;dirty=false;await reload();if(!current(pid,gen))return;await loadReport(result.id);if(current(pid,gen))message('Versión '+result.version+' guardada. Las versiones anteriores se conservan.');}
  catch(e){if(current(pid,gen))message(e.message);}finally{busy=false;controls();}});
 byId('reportPublish').onclick=async()=>{if(busy||!canPublish||!selected||dirty||selected.version!==selected.current_version||selected.version===selected.published_version)return;
  const id=selected.id,version=selected.version,pid=getProject(),gen=generation;busy=true;controls();try{await api(prefix()+'/'+id+'/release',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version:version})});if(!current(pid,gen))return;await reload();if(!current(pid,gen))return;await loadReport(id);if(current(pid,gen))message('Esta versión ya puede consultarse por los lectores del proyecto.');}
  catch(e){if(current(pid,gen))message(e.message);}finally{busy=false;controls();}};
 byId('reportVersions').onclick=async()=>{if(!selected||busy)return;const id=selected.id,pid=getProject(),gen=generation,token=openSequence;
  try{const rows=await api(prefix()+'/'+id+'/versions');if(!current(pid,gen)||token!==openSequence||selected?.id!==id)return;const list=byId('reportVersionList');list.replaceChildren();for(const r of rows){const button=el('button','Versión '+r.version+' · '+stamp(r.created_at),'outline');button.type='button';button.onclick=()=>open(id,r.version).catch(e=>message(e.message));list.append(button);}}
  catch(e){if(current(pid,gen))message(e.message);}};
 async function exportFile(document){if(!selected||busy)return;const id=selected.id,version=selected.version,pid=getProject(),gen=generation,token=openSequence;
  try{const result=await api(prefix()+'/'+id+'/versions/'+version+(document?'/document':'/export'));if(!current(pid,gen)||token!==openSequence)return;
   const blob=new Blob([document?result.html:JSON.stringify(result,null,2)],{type:document?'text/html;charset=utf-8':'application/json'}),url=URL.createObjectURL(blob);if(!current(pid,gen)||token!==openSequence){URL.revokeObjectURL(url);return;}const link=el('a');link.href=url;link.download='NEXO_Informe_'+id+'_v'+version+(document?'.html':'.json');link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  catch(e){if(current(pid,gen)&&token===openSequence)message(e.message);}}
 byId('reportExport').onclick=()=>exportFile(false);byId('reportDocument').onclick=()=>exportFile(true);
 byId('reportOrigin').onclick=()=>{if(!selected||!safeToLeave())return;page(kind(selected.snapshot)==='briefing'?'summary':kind(selected.snapshot)==='selection'?'listening':'knowledge');};
 function prepare(question='',source='all',scope=null){if(!safeToLeave())return;clear();documentId=scope;byId('reportQuestion').value=question;byId('reportKind').value=source;dirty=!!question;controls();page('reports');message(canWrite?'Completa el título y la nota para recuperar las fuentes.':'Tu cuenta permite consultar las versiones habilitadas.');}
 byId('summaryPrepare').onclick=()=>prepare();byId('reportSearch').oninput=renderList;for(const id of ['reportStateFilter','reportTypeFilter'])byId(id).onchange=renderList;
 byId('reportRefresh').onclick=()=>reload().catch(e=>message(e.message));
 function resetProject(){generation++;listSequence++;openSequence++;canWrite=false;canPublish=false;archive=[];clear();byId('reportSearch').value='';byId('reportStateFilter').value='all';byId('reportTypeFilter').value='all';byId('reportList').replaceChildren();byId('reportListNote').textContent='';byId('reportFilteredCount').textContent='';byId('summaryReports').textContent='—';message('');for(const id of ['reportCount','reportDraftCount','reportReleasedCount','reportUpdatedCount'])byId(id).textContent='—';}
 return {reload,prepare,resetProject,open,canLeaveProject:safeToLeave};
}};
