/* Local content review. Provider keys and authentication tokens stay outside this module. */
window.NexoReviews={install({api,byId,page,getProject}){
 const labels={unreviewed:'Sin revisar',reviewed:'Revisado documentalmente',needs_check:'Por verificar'};
 let topics=[],articles=[],canManage=false,canReview=false,current=null,sequence=0,dirty=false;
 const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
 const message=text=>{byId('reviewMessage').textContent=text;const target=byId('settingsTopicsStatus');if(target)target.textContent=text;};
 const askDiscard=()=>!dirty||confirm('Tienes cambios sin guardar. ¿Quieres descartarlos?');
 const prefix=()=>`/api/projects/${getProject()}`;
 function renderTopics(){
  const list=byId('topicCatalog');list.replaceChildren();byId('topicCreateButton').disabled=!canManage;byId('topicName').disabled=!canManage;
  if(!topics.length)list.append(el('p','Aún no hay temas. Un administrador puede crear el primero.','note'));
  for(const topic of topics){const row=el('div',undefined,'topic-row');const name=el('input');name.value=topic.name;name.maxLength=80;name.setAttribute('aria-label','Nombre del tema '+topic.name);name.disabled=!canManage;row.append(name);
   const rename=el('button','Guardar nombre','outline');rename.type='button';rename.disabled=!canManage;
   const toggle=el('button',topic.active?'Archivar':'Reactivar','outline');toggle.type='button';toggle.disabled=!canManage;
   async function change(active){if(!askDiscard())return;rename.disabled=true;toggle.disabled=true;
    try{await api(prefix()+'/topics/'+topic.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name.value,active,expected_version:topic.version})});dirty=false;await reload();message('Tema actualizado. Su historial se conserva.');}
    catch(error){message(error.message);rename.disabled=!canManage;toggle.disabled=!canManage;}}
   rename.onclick=()=>change(topic.active);toggle.onclick=()=>change(!topic.active);
   row.append(rename,toggle,el('small',topic.active?'Activo':'Archivado','note'));list.append(row);
  }
 }
 function clearEditor(){current=null;dirty=false;byId('reviewEditor').hidden=true;byId('reviewEmpty').hidden=false;byId('reviewHistory').replaceChildren();}
 function choose(article){
  if(!askDiscard())return;current=article;dirty=false;byId('reviewEditor').hidden=false;byId('reviewEmpty').hidden=true;
  byId('reviewSelectedTitle').textContent=article.title;byId('reviewSelectedMeta').textContent=article.publisher+' · versión '+article.review.version;
  const link=byId('reviewOriginal');link.hidden=!/^https:\/\//i.test(article.url||'');if(!link.hidden)link.href=article.url;
  byId('reviewStatus').value=article.review.status;byId('reviewNote').value=article.review.note;byId('reviewNote').disabled=!canReview;byId('reviewStatus').disabled=!canReview;byId('reviewSave').disabled=!canReview;
  const selected=new Set(article.review.topics.map(t=>t.id));const list=byId('reviewTopicChoices');list.replaceChildren();
  for(const topic of topics.filter(t=>t.active||selected.has(t.id))){const label=el('label');const input=el('input');input.type='checkbox';input.value=topic.id;input.checked=selected.has(topic.id);input.disabled=!canReview;input.onchange=()=>{dirty=true;};label.append(input,document.createTextNode(' '+topic.name+(topic.active?'':' (archivado)')));list.append(label);}
  if(!list.children.length)list.append(el('p','Crea un tema para poder etiquetar. Puedes guardar una revisión sin etiquetas.','note'));
  byId('reviewHistory').replaceChildren();message(canReview?'Revisa la fuente y guarda tus cambios.':'Tu rol permite consultar; no editar revisiones.');
 }
 function renderArticles(truncated){
  const list=byId('reviewArticles');list.replaceChildren();byId('reviewCount').textContent=`${articles.length} publicaciones mostradas`+(truncated?' · se aplicó el límite de 100':'');
  if(!articles.length)list.append(el('p','No hay publicaciones que coincidan con estos filtros.','note'));
  for(const article of articles){const card=el('article',undefined,'review-article');card.append(el('b',article.title),el('p',article.publisher+' · '+labels[article.review.status],'note'));
   const names=article.review.topics.map(t=>t.name+(t.active?'':' (archivado)'));card.append(el('p',names.length?names.join(' · '):'Sin temas asignados','note'));
   const open=el('button','Abrir revisión','outline');open.type='button';open.onclick=()=>choose(article);card.append(open);list.append(card);
  }
 }
 async function reload(){
  if(!getProject())return;const order=++sequence;const project=getProject();const selectedId=current?.id;
  const filters=new URLSearchParams({q:byId('reviewQuery').value.trim(),status:byId('reviewFilter').value,topic_id:byId('reviewTopicFilter').value});
  const [catalog,data]=await Promise.all([api(prefix()+'/topics'),api(prefix()+'/reviews?'+filters)]);
  if(order!==sequence||project!==getProject())return;
  topics=catalog.topics;articles=data.articles;canManage=catalog.can_manage;canReview=catalog.can_review;
  const filter=byId('reviewTopicFilter'),chosen=filter.value;filter.replaceChildren(new Option('Todos los temas','0'));
  for(const topic of topics)filter.add(new Option(topic.name+(topic.active?'':' (archivado)'),String(topic.id)));
  filter.value=topics.some(t=>String(t.id)===chosen)?chosen:'0';renderTopics();renderArticles(data.truncated);
  const found=articles.find(a=>a.id===selectedId);dirty=false;if(found)choose(found);else clearEditor();
 }
 byId('topicCreate').onsubmit=async event=>{event.preventDefault();if(!askDiscard())return;byId('topicCreateButton').disabled=true;
  try{await api(prefix()+'/topics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:byId('topicName').value})});byId('topicName').value='';dirty=false;await reload();message('Tema guardado. Puedes asignarlo a una publicación.');}
  catch(error){message(error.message);}finally{byId('topicCreateButton').disabled=!canManage;}};
 byId('reviewNote').oninput=()=>{dirty=true;};byId('reviewStatus').onchange=()=>{dirty=true;};
 byId('reviewSearchForm').onsubmit=event=>{event.preventDefault();if(askDiscard()){dirty=false;reload().catch(error=>message(error.message));}};
 byId('reviewSaveForm').onsubmit=async event=>{event.preventDefault();if(!current)return;const button=byId('reviewSave');button.disabled=true;
  const topicIds=Array.from(byId('reviewTopicChoices').querySelectorAll('input:checked')).map(n=>Number(n.value));
  try{await api(prefix()+'/reviews/'+current.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_version:current.review.version,topic_ids:topicIds,status:byId('reviewStatus').value,note:byId('reviewNote').value})});dirty=false;await reload();message('Revisión guardada y registrada en el historial.');}
  catch(error){message(error.message+' Tus cambios siguen en el formulario.');}finally{button.disabled=!canReview;}};
 byId('reviewLoadHistory').onclick=async()=>{if(!current)return;const articleId=current.id;
  try{const data=await api(prefix()+'/reviews/'+articleId+'/history');if(current?.id!==articleId)return;const list=byId('reviewHistory');list.replaceChildren();
   if(!data.changes.length)list.append(el('p','Esta publicación todavía no tiene cambios guardados.','note'));
   for(const change of data.changes){const card=el('article',undefined,'review-article');card.append(el('b','Versión '+change.version+' · '+labels[change.status]),el('p','Usuario #'+change.actor_id+' · '+new Date(change.created_at).toLocaleString('es-MX'),'note'),el('p',change.topics.map(t=>t.name).join(' · ')||'Sin temas','note'),el('p',change.note||'Sin nota'));list.append(card);}
   if(data.truncated)list.append(el('p','Se muestran las últimas 100 versiones.','note'));
  }catch(error){message(error.message);}};
 function resetProject(){sequence++;topics=[];articles=[];canManage=false;canReview=false;clearEditor();for(const id of ['topicCatalog','reviewArticles'])byId(id).replaceChildren();byId('topicName').value='';byId('reviewQuery').value='';byId('reviewNote').value='';}
 return {reload,resetProject,canLeaveProject:askDiscard};
}};
