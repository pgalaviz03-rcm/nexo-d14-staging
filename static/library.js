/* A document-first library. Text stays literal and asynchronous work is scoped. */
window.NexoLibrary={install({api,byId,getProject,onScopeChange,onSearchFocus,onConfigureDocument=null,onAddDocument=null}){
 let generation=0,sequence=0,pageSequence=0,items=[],canPrepare=false,busy=false;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const current=(pid,gen)=>pid===getProject()&&gen===generation;
 const prefix=()=>'/api/projects/'+getProject()+'/library';
 const labels={ready:'Listo para buscar',partial:'Texto disponible · algunas páginas sin texto',needs_prepare:'Preparar para buscar',needs_ocr:'Necesita reconocimiento de texto',stored:'Archivo guardado'};
 const selectedId=()=>Number(byId('knowledgeDocument').value)||null;
 const message=text=>{byId('libraryStatus').textContent=text;};
 function clearReader(){pageSequence++;byId('libraryReader').hidden=true;byId('libraryPageText').textContent='';}
 function select(id){const item=items.find(r=>r.id===Number(id)&&r.searchable);byId('knowledgeDocument').value=item?String(item.id):'';
  if(item)byId('knowledgeKind').value='documents';clearReader();onScopeChange();
  byId('knowledgeScope').textContent=item?'Buscando únicamente en: '+item.filename:'Busca en todas las fuentes del proyecto o elige un documento.';
 }
 function controls(){byId('libraryAdd').hidden=!canPrepare;byId('libraryAdd').disabled=busy;byId('libraryRefresh').disabled=busy;
  for(const root of [byId('libraryDocuments'),byId('datasetsList')])for(const button of root.querySelectorAll('button'))button.disabled=busy;
 }
 function renderInto(root){root.replaceChildren();for(const item of items){const card=el('article',undefined,'dataset-item');
   const head=el('div',undefined,'dataset-top');head.append(el('b',item.filename,'dataset-name'),el('span',labels[item.state]||'Archivo guardado','dataset-badge'+(item.searchable?'':' pending')));card.append(head);
   card.append(el('p',item.format+' · '+(item.size_bytes/1024).toFixed(1)+' KB'+(item.pages?' · '+item.pages+' páginas':''),'note'));
   const actions=el('div',undefined,'actions');
   if(item.searchable){const search=el('button','Buscar en este documento','outline');search.type='button';search.onclick=()=>{select(item.id);onSearchFocus();byId('knowledgeQuery').focus();};actions.append(search);}
   if(item.format==='PDF'&&item.pages){const read=el('button','Leer texto por página','outline');read.type='button';read.onclick=()=>{select(item.id);onSearchFocus();readPage(item.id,1);};actions.append(read);}
   if(item.state==='needs_prepare'&&canPrepare){const prepare=el('button','Preparar para buscar','solid');prepare.type='button';prepare.onclick=()=>prepareDocument(item.id);actions.append(prepare);}
   if(item.state==='needs_ocr')card.append(el('p','No se encontró texto seleccionable. Necesita reconocimiento de texto para poder buscar.','note'));
   if(item.format==='XLSX'&&!item.searchable&&canPrepare){const choose=el('button','Elegir filas y columnas','outline');choose.type='button';choose.onclick=()=>{if(onConfigureDocument){onConfigureDocument(item.id);return;}onSearchFocus();byId('workbookTools').open=true;byId('workbookTools').scrollIntoView({block:'start',behavior:'smooth'});};actions.append(choose);}
   card.append(actions);root.append(card);
  }if(!items.length)root.append(el('p','Añade tu primer documento para buscar palabras y conservar sus fuentes.','empty-dataset'));
 }
 async function reload(){const pid=getProject();if(!pid)return;const gen=generation,token=++sequence;
  const result=await api(prefix()+'/documents');if(!current(pid,gen)||token!==sequence)return;
  const previous=selectedId();items=result.items;canPrepare=result.can_prepare;
  const selectBox=byId('knowledgeDocument');selectBox.replaceChildren();const all=el('option','Todos los documentos');all.value='';selectBox.append(all);
  for(const item of items){const option=el('option',item.filename+(item.searchable?'':' · '+labels[item.state]));option.value=String(item.id);option.disabled=!item.searchable;selectBox.append(option);}
  selectBox.value=items.some(r=>r.id===previous&&r.searchable)?String(previous):'';
  if(previous&&!selectedId()){clearReader();onScopeChange();byId('knowledgeScope').textContent='El documento seleccionado necesita revisión; elige otro archivo.';}
  renderInto(byId('libraryDocuments'));renderInto(byId('datasetsList'));controls();byId('sourceRegisteredCount').textContent=String(items.length);
  message(items.length+' documentos · '+items.filter(r=>r.searchable).length+' listos para buscar'+(result.bounded?' · Se muestra un máximo de 500 registros.':''));return result;
 }
 async function prepareDocument(id){if(busy||!canPrepare)return;const pid=getProject(),gen=generation;busy=true;controls();message('Preparando el texto del documento…');
  try{const result=await api(prefix()+'/documents/'+id+'/prepare',{method:'POST'});if(!current(pid,gen))return;await reload();if(!current(pid,gen))return;
   if(result.searchable){select(id);onSearchFocus();message('Listo. Escribe una palabra para buscar en este documento.');}else message('Este PDF necesita reconocimiento de texto antes de buscar.');
  }catch(e){if(current(pid,gen))message(e.message);}finally{busy=false;controls();}
 }
 async function uploadFile(file){if(busy||!file||!canPrepare)return;const pid=getProject(),gen=generation;busy=true;controls();message('Guardando y preparando tu documento…');
  try{const form=new FormData();form.append('file',file);const result=await api(prefix()+'/upload',{method:'POST',body:form});if(!current(pid,gen))return;
   await reload();if(!current(pid,gen))return;const item=items.find(r=>r.id===result.id);if(item?.searchable)select(item.id);onSearchFocus();message(result.detail);
   return result;
  }catch(e){if(current(pid,gen))message(e.message);throw e;}finally{busy=false;controls();byId('libraryFile').value='';}
 }
 async function readPage(id,number){const pid=getProject(),gen=generation,token=++pageSequence;byId('libraryReader').hidden=false;byId('libraryPageText').textContent='Leyendo página…';
  for(const button of ['libraryPrevious','libraryNext'])byId(button).disabled=true;
  try{const result=await api(prefix()+'/documents/'+id+'/pages/'+number);if(!current(pid,gen)||token!==pageSequence)return;
   byId('libraryPageTitle').textContent=result.filename+' · página '+result.page+' de '+result.pages;
   byId('libraryPageText').textContent=result.text||'Esta página no contiene texto extraíble. Puede contener imágenes o gráficos.';
   byId('libraryPrevious').disabled=result.page<=1;byId('libraryNext').disabled=result.page>=result.pages;
   byId('libraryPrevious').onclick=()=>readPage(id,result.page-1);byId('libraryNext').onclick=()=>readPage(id,result.page+1);
  }catch(e){if(current(pid,gen)&&token===pageSequence)byId('libraryPageText').textContent=e.message;}
 }
 byId('knowledgeDocument').onchange=()=>select(selectedId());
 byId('knowledgeKind').onchange=()=>{if(byId('knowledgeKind').value!=='documents')select(null);else onScopeChange();};
 byId('libraryRefresh').onclick=()=>reload().catch(e=>message(e.message));
 byId('libraryAdd').onclick=()=>onAddDocument?onAddDocument():byId('libraryFile').click();
 byId('libraryFile').onchange=()=>uploadFile(byId('libraryFile').files[0]).catch(()=>{});
 function resetProject(){generation++;sequence++;items=[];canPrepare=false;busy=false;clearReader();
  for(const id of ['libraryDocuments','datasetsList','knowledgeDocument'])byId(id).replaceChildren();byId('knowledgeDocument').value='';byId('knowledgeScope').textContent='';message('');controls();}
 return {reload,selectedId,select,uploadFile,resetProject,canLeaveProject:()=>!busy};
}};
