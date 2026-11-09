/* Local workbook selections. Original bytes and historical metrics stay separate. */
window.NexoWorkbooks={install({api,byId,getProject,onPrepared}){
 let generation=0,structure=null,preview=null,canExtract=false,saving=false;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const controls=['workbookFile','workbookSheet','workbookColumns','workbookHeader','workbookFirst','workbookLast','workbookYear','workbookNote'];
 const status=text=>byId('workbookStatus').textContent=text;
 const base=()=>'/api/projects/'+getProject()+'/library/workbooks';
 function clearPreview(){preview=null;byId('workbookPreview').replaceChildren();byId('workbookExtract').disabled=true;}
 function invalidate(){generation++;clearPreview();}
 function selection(){const columns=byId('workbookColumns').value.toUpperCase().split(/[\s,;]+/).filter(Boolean);
  if(!columns.length||columns.some(c=>!/^[A-Z]{1,2}$/.test(c))||new Set(columns).size!==columns.length)throw Error('Indica columnas sin repetir, por ejemplo A,B,C.');
  return {sheet:byId('workbookSheet').value,columns,header_row:Number(byId('workbookHeader').value||1),first_row:Number(byId('workbookFirst').value||2),last_row:Number(byId('workbookLast').value||5000),source_year:byId('workbookYear').value?Number(byId('workbookYear').value):null,source_note:byId('workbookNote').value.trim()};
 }
 function useSheet(){invalidate();const s=structure?.sheets.find(s=>s.name===byId('workbookSheet').value);byId('workbookColumns').value=s?s.columns.map(c=>c.column).join(','):'';byId('workbookLast').value=String(s?.max_row||5000);status(s?s.rows+' filas con datos · '+s.formula_count+' fórmulas con valores del archivo.':'');}
 async function inspect(){if(saving)return;const pid=getProject(),id=byId('workbookFile').value,token=++generation;clearPreview();structure=null;byId('workbookSheet').replaceChildren();byId('workbookRead').disabled=true;
  if(!id){status('Añade un libro desde Configuración → Datos e importaciones.');return;}
  try{const result=await api(base()+'/'+id);if(pid!==getProject()||token!==generation)return;structure=result;for(const s of result.sheets){const o=el('option',s.name);o.value=s.name;byId('workbookSheet').append(o);}byId('workbookSheet').value=result.sheets[0]?.name||'';useSheet();byId('workbookRead').disabled=false;
  }catch(e){if(pid===getProject()&&token===generation)status(e.message);}
 }
 async function reload(){if(saving)return;const pid=getProject(),token=++generation;clearPreview();structure=null;canExtract=false;byId('workbookFile').replaceChildren();byId('workbookSheet').replaceChildren();byId('workbookRead').disabled=true;status('');if(!pid)return;
  try{const p=await api(base());if(pid!==getProject()||token!==generation)return;canExtract=p.can_extract;byId('workbookExtract').hidden=!canExtract;
   for(const f of p.items){const o=el('option',f.filename);o.value=String(f.id);byId('workbookFile').append(o);}byId('workbookFile').value=p.items.length?String(p.items[0].id):'';
   if(p.items.length)await inspect();else status('Los libros del proyecto aparecerán aquí después de añadirlos.');
  }catch(e){if(pid===getProject()&&token===generation)status(e.message);}
 }
 byId('workbookFile').onchange=inspect;byId('workbookSheet').onchange=()=>{if(!saving)useSheet();};
 for(const id of controls.filter(id=>!['workbookFile','workbookSheet'].includes(id)))byId(id).oninput=()=>{if(!saving)invalidate();};
 byId('workbookRead').onclick=async()=>{if(saving||!structure)return;const pid=getProject(),token=++generation,id=byId('workbookFile').value;clearPreview();status('Preparando la selección…');
  try{const body=selection(),p=await api(base()+'/'+id+'/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(pid!==getProject()||token!==generation)return;
   preview={packet:p,body,id};status(p.metadata.row_count+' filas en la selección · vista previa de las primeras '+p.preview.length+'.');
   for(const row of p.preview){const card=el('article');card.className='dataset-item';card.append(el('b',row.location));for(const c of row.cells)card.append(el('p',c.label+' ['+c.cell+']: '+(c.value===null?'Sin dato':c.value)));byId('workbookPreview').append(card);}byId('workbookExtract').disabled=!canExtract;
  }catch(e){if(pid===getProject()&&token===generation)status(e.message);}
 };
 byId('workbookExtract').onclick=async()=>{if(saving||!canExtract||!preview)return;const pid=getProject(),token=generation,p=preview;
  try{if(JSON.stringify(selection())!==JSON.stringify(p.body)){invalidate();status('Revisa de nuevo la selección antes de guardarla.');return;}}
  catch(e){invalidate();status(e.message);return;}
  saving=true;for(const id of controls)byId(id).disabled=true;byId('workbookRead').disabled=true;byId('workbookExtract').disabled=true;
  try{const r=await api(base()+'/'+p.id+'/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...p.body,preview_sha256:p.packet.preview_sha256})});
   if(pid!==getProject()||token!==generation)return;await onPrepared();if(pid!==getProject()||token!==generation)return;
   clearPreview();status(r.deduplicated?'Esta selección ya está disponible para buscar.':r.rows+' filas preparadas para consultar en la biblioteca.');
  }catch(e){if(pid===getProject()&&token===generation)status(e.message);}finally{saving=false;for(const id of controls)byId(id).disabled=false;byId('workbookRead').disabled=!structure;if(pid===getProject()&&token===generation)byId('workbookExtract').disabled=!preview;}
 };
 function resetProject(){generation++;clearPreview();structure=null;canExtract=false;byId('workbookFile').replaceChildren();byId('workbookSheet').replaceChildren();byId('workbookExtract').hidden=true;byId('workbookRead').disabled=true;
  for(const id of ['workbookColumns','workbookYear','workbookNote'])byId(id).value='';byId('workbookHeader').value='1';byId('workbookFirst').value='2';byId('workbookLast').value='5000';status('');}
 return {select:id=>{byId('workbookFile').value=String(id);return inspect();},reload,resetProject,canLeaveProject:()=>!saving};
}};
