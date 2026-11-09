import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const script=fs.readFileSync(new URL('../static/evidence_cards.js',import.meta.url),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.open=false;}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}set innerHTML(x){throw Error('Untrusted HTML');}}
const document={createElement:t=>new Element(t)},window={};vm.runInNewContext(script,{window,document,URL,Number,String});
const root=new Element(),cases=[],check=(name,fn)=>{fn();cases.push(name);},text=n=>[n.textContent,...n.children.map(text)].join(' ');
const row={citation:'D2:R2',record_type:'workbook_row',title:'Sección 158',source:'Libro.xlsx · Hoja1 · fila 2',excerpt:'Sección: 158\nLista nominal: 438',
 display_fields:[{label:'Sección',original_label:'SECCION 736',value:'158',cell:'A2'},{label:'Distrito',value:'14',cell:'B2'},{label:'Colonia de referencia',value:'PRIMO VERDAD INEGI',cell:'E2'},{label:'Lista nominal',value:'438',cell:'F2'}],
 workbook_origin:{filename:'Libro.xlsx',sheet:'Hoja1',row:2,cells:['A2','B2','E2','F2'],source_year_declared:2024,source_note_declared:'Aportado por proyecto',sha256:'f'.repeat(64)}};
window.NexoEvidenceCards.render(root,{citations:[row]});const card=root.children[0],detail=card.children.find(n=>n.tagName==='details'),visible=card.children.filter(n=>n.tagName!=='details').map(text).join(' ');
check('one_row_produces_one_card',()=>assert.equal(root.children.length,1));
check('requested_section_is_the_card_title',()=>assert(card.children.some(n=>n.tagName==='h3'&&n.textContent==='Sección 158')));
check('main_card_contains_plain_fields_and_value',()=>{assert(visible.includes('PRIMO VERDAD INEGI'));assert(visible.includes('438'));});
check('technical_hash_and_wrong_header_are_outside_main_card',()=>{assert(!visible.includes('f'.repeat(64)));assert(!visible.includes('736'));assert(!visible.includes('Archivo de origen'));});
check('origin_is_folded_and_explicitly_labeled',()=>{assert.equal(detail.open,false);assert.equal(detail.children[0].textContent,'Ver origen y celdas');});
check('origin_preserves_sheet_row_cells_and_original_header',()=>{const s=text(detail);for(const value of ['Hoja1','Fila: 2','A2','F2','SECCION 736'])assert(s.includes(value));});
check('year_is_marked_declared',()=>assert(visible.includes('2024 (año declarado)')));
const changed=structuredClone(row);changed.display_fields[3].value=null;window.NexoEvidenceCards.render(root,{citations:[changed]});
check('missing_value_is_not_zero',()=>assert(text(root).includes('Sin dato')));
changed.display_fields[3].value='0';window.NexoEvidenceCards.render(root,{citations:[changed]});
check('real_zero_is_displayed',()=>assert(!text(root).includes('Sin dato')));
changed.display_fields[3].value='1234';window.NexoEvidenceCards.render(root,{citations:[changed]});
check('large_counter_is_readable_without_rounding',()=>assert(text(root).includes('1,234')));
changed.display_fields[2].value='<img src=x onerror=bad>';window.NexoEvidenceCards.render(root,{citations:[changed]});
check('cell_content_is_literal_text',()=>assert(text(root).includes('<img src=x onerror=bad>')));
window.NexoEvidenceCards.render(root,{citations:[row,{...structuredClone(row),title:'Sección 211'}]});
check('different_rows_remain_separate',()=>assert.equal(root.children.length,2));
window.NexoEvidenceCards.render(root,{citations:[{title:'Noticia',source:'Medio',excerpt:'Texto <b>literal</b>',url:'javascript:bad'}]});
check('ordinary_sources_still_render_with_unsafe_links_dropped',()=>{assert(text(root).includes('Texto <b>literal</b>'));assert(!root.children[0].children.some(n=>n.tagName==='a'));});
window.NexoEvidenceCards.render(root,{citations:[]});check('new_empty_cut_clears_previous_cards',()=>assert.equal(root.children.length,0));
console.log(JSON.stringify({passed:true,cases,browser_rendering:false}));
