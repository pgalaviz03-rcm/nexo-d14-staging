/* User-facing evidence: one workbook row per card; origin remains expandable. */
window.NexoEvidenceCards={render(root,packet){
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 root.replaceChildren();
 for(const item of packet.citations){const card=el('article',undefined,'evidence-card');
  if(item.record_type==='workbook_row'){
   card.append(el('div','REGISTRO DEL PROYECTO','eyebrow'),el('h3',item.title));
   const grid=el('dl',undefined,'evidence-fields');
   for(const field of item.display_fields){let value=field.value===null||field.value===undefined?'Sin dato':String(field.value);
    if(field.label==='Lista nominal'&&/^\d+$/.test(value)&&Number.isSafeInteger(Number(value)))value=Number(value).toLocaleString('es-MX');
    const pair=el('div');pair.append(el('dt',field.label),el('dd',value));grid.append(pair);
   }card.append(grid);
   const o=item.workbook_origin||{};card.append(el('p',(o.filename||item.source)+(o.source_year_declared?' · '+o.source_year_declared+' (año declarado)':''),'note'));
   const detail=el('details',undefined,'evidence-origin');detail.append(el('summary','Ver origen y celdas'));
   detail.append(el('p','Hoja: '+(o.sheet||'—')+' · Fila: '+(o.row??'—')),el('p','Celdas: '+(o.cells||[]).join(', ')));
   if(o.source_note_declared)detail.append(el('p','Procedencia declarada: '+o.source_note_declared));
   for(const f of item.display_fields)if(f.original_label&&f.original_label!==f.label)detail.append(el('p',f.cell+': encabezado original «'+f.original_label+'».'));
   detail.append(el('small','Referencia: '+item.citation));if(o.sha256)detail.append(el('p','Huella del original: '+o.sha256,'evidence-hash'));
   card.append(detail);
  }else{
   card.append(el('h3',item.title),el('small',item.source),el('p',item.excerpt,'evidence-excerpt'));
   if(item.record_type==='pdf_page'){
    const origin=el('details',undefined,'evidence-origin');origin.append(el('summary','Ver origen y página'));
    origin.append(el('p','Página '+item.page+' de '+item.pdf_origin.pages),el('small','Referencia: '+item.citation));
    origin.append(el('p','Huella del original: '+item.pdf_origin.sha256,'evidence-hash'));card.append(origin);
   }
   if(item.url){try{const u=new URL(item.url);if(u.protocol==='https:'&&!u.username&&!u.password){const a=el('a','Ver fuente original ↗');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';card.append(a);}}catch{}}
  }
  root.append(card);
 }
}};
