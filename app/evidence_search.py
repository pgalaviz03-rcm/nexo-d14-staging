"""Readable row-level workbook retrieval; protected lexical module stays unchanged."""
import hashlib,json,re
from collections import Counter
from pathlib import Path
from decimal import Decimal,InvalidOperation
from sqlalchemy import select
from fastapi import HTTPException
from .models import Dataset
from . import knowledge as legacy
from .news_review import query_articles,iso_utc
from .workbook_api import source_bytes,WorkbookSelection
from .workbook_evidence import CONTRACT,prepare,WorkbookInvalid,digest
from .library_api import pdf_packet,original_bytes
from .pdf_evidence import CONTRACT as PDF_CONTRACT

QUESTION_WORDS={'fue','fueron','son','era','eran','sea','ser','tiene','tienen','esta','estan','este','estos',
 'esa','esas','ese','esos','cual','cuanto','cuanta','cuantos','cuantas','donde','quien','quienes',
 'segun','archivo','archivos','pdf','dice','decir','indica','indicame','muestra','muestrame','puedes',
 'podrias','necesito','quiero','saber'}
def search_terms(question):
 terms=[t for t in legacy.terms(question) if t not in QUESTION_WORDS]
 if not terms:raise ValueError('Escribe una palabra concreta del tema o el número de sección.')
 return terms
def word_counts(value):
 return Counter(re.findall(r'\w+',legacy.normalized(value).replace('_',' ')))

def section_header(label):
 return bool(re.fullmatch(r'seccion(?:\s+(?:electoral|numero|\d+))?',legacy.normalized(label.strip())))

def section_query(question):
 q=legacy.normalized(question)
 m=re.search(r'\bseccion(?:\s+(?:electoral|numero|no\.?))?\s*[:#º°.-]?\s*(\d{1,6})\b',q)
 if m:return int(m[1])
 return int(q.strip()) if re.fullmatch(r'\s*\d{1,6}\s*',q) else None

def section_value(value):
 try:
  if value is None or not re.fullmatch(r'\d+(?:\.0+)?',value.strip()):return None
  return int(Decimal(value))
 except (ValueError,InvalidOperation,OverflowError):return None

def label_name(label):
 if section_header(label):return 'Sección'
 return {'dl':'Distrito','lista nominal':'Lista nominal','colonia de referencia':'Colonia de referencia'}.get(legacy.normalized(label.strip()),label.strip())

def workbook_rows(session,pid,item,uploads):
 """Verify source, sidecar and reproducibility before using structured records."""
 try:
  meta=json.loads(item.detail.split('\n',1)[1])
  source,raw=source_bytes(session,pid,meta['source_dataset_id'],uploads)
  saved,error=legacy.document_bytes(session,item,uploads)
  if error or source.sha256!=meta['source_sha256'] or item.sha256!=meta['text_sha256']:return None
  keys=('sheet','columns','header_row','first_row','last_row','source_year','source_note')
  selection=WorkbookSelection(**{k:meta[k] for k in keys});packet=prepare(raw,source.filename,selection)
  if packet['metadata']['text_sha256']!=item.sha256 or packet['preview_sha256']!=meta['preview_sha256']:return None
  return source,meta,packet['records']
 except (ValueError,KeyError,IndexError,TypeError,HTTPException,WorkbookInvalid):return None

def row_citation(pid,item,source,meta,row):
 fields=[dict(label=label_name(c['label']),original_label=c['label'],value=c['value'],cell=c['cell']) for c in row['cells']]
 idcell=next((c for c in row['cells'] if section_header(c['label'])),None)
 identifier=idcell['value'] if idcell else None
 title='Sección '+identifier if identifier is not None else source.filename+' · fila '+str(row['row'])
 excerpt='\n'.join(c['label']+': '+(c['value'] if c['value'] is not None else 'Sin dato') for c in fields)
 origin=dict(filename=source.filename,sha256=source.sha256,text_sha256=item.sha256,source_dataset_id=source.id,
  sheet=meta['sheet'],row=row['row'],columns=meta['columns'],cells=[c['cell'] for c in fields],location=row['location'],
  source_year_declared=meta['source_year'],source_note_declared=meta['source_note'])
 return dict(citation=f'D{item.id}:R{row["row"]}',project_id=pid,kind='document',dataset_id=item.id,title=title,
  source=source.filename+' · '+meta['sheet']+' · fila '+str(row['row']),url=None,excerpt=excerpt,offset=row['row'],
  display_fields=fields,workbook_origin=origin,content_sha256=digest(dict(excerpt=excerpt,origin=origin)),
  record_type='workbook_row')

def retrieve_context(session,pid,question,uploads,*,limit=5,source_kind='all',days=0,document_id=None):
 if len(question)>240 or not 1<=limit<=8 or source_kind not in {'all','news','documents'} or days not in {0,1,7,30}:
  raise ValueError('Consulta o límite no admitido.')
 selected_document=None
 if document_id is not None:
  if type(document_id) is not int or document_id<1:raise ValueError('Documento no válido.')
  selected_document,_=original_bytes(session,pid,document_id,uploads)
  if selected_document.detail.startswith((CONTRACT+'\n',PDF_CONTRACT+'\n')):
   raise HTTPException(422,'Elige el archivo original en Biblioteca.')
  source_kind='documents'
 wanted=search_terms(question);target=section_query(question)
 candidates=[];skipped=[];available=[];bounded=False;news_scanned=documents_scanned=0
 if source_kind in {'all','news'}:
  news=session.scalars(query_articles(pid,days=days).limit(legacy.MAX_NEWS+1)).all();bounded=len(news)>legacy.MAX_NEWS
  for r in news[:legacy.MAX_NEWS]:
   news_scanned+=1;excerpt=(r.title+'\n'+r.abstract)[:2000]
   candidates.append(dict(citation=f'N{r.id}',project_id=pid,kind='news',title=r.title,source=r.publisher,url=r.url,
    excerpt=excerpt,published_at=iso_utc(r.published_at),content_sha256=hashlib.sha256(excerpt.encode()).hexdigest()))
 if source_kind in {'all','documents'}:
  query=select(Dataset).where(Dataset.project_id==pid,~Dataset.detail.startswith(PDF_CONTRACT+'\n'))
  if document_id is not None:
   # A selected original must never disappear behind other files or selections.
   docs=[selected_document]
   if Path(selected_document.filename).suffix.lower()=='.xlsx':
    sidecars=session.scalars(query.where(Dataset.detail.startswith(CONTRACT+'\n')).order_by(Dataset.id.desc()).limit(501)).all()
    linked=[];bounded=bounded or len(sidecars)>500
    for sidecar in sidecars[:500]:
     try:
      if json.loads(sidecar.detail.split('\n',1)[1]).get('source_dataset_id')==document_id:linked.append(sidecar)
     except (ValueError,IndexError,TypeError):continue
    bounded=bounded or len(linked)>=legacy.MAX_DOCUMENTS
    docs=linked[:legacy.MAX_DOCUMENTS-1]+docs
  else:docs=session.scalars(query.order_by(Dataset.id.desc()).limit(legacy.MAX_DOCUMENTS+1)).all()
  bounded=bounded or len(docs)>legacy.MAX_DOCUMENTS
  for doc in docs[:legacy.MAX_DOCUMENTS]:
   if doc.detail.startswith(PDF_CONTRACT+'\n'):continue
   if document_id is not None and doc.id!=document_id:
    try:
     if json.loads(doc.detail.split('\n',1)[1])['source_dataset_id']!=document_id:continue
    except (ValueError,KeyError,IndexError):continue
   documents_scanned+=1
   if Path(doc.filename).suffix.lower()=='.pdf':
    packet=pdf_packet(session,pid,doc,uploads)
    if not packet:skipped.append(dict(dataset_id=doc.id,reason='pdf_needs_prepare'));continue
    if not packet['text_chars']:skipped.append(dict(dataset_id=doc.id,reason='pdf_needs_ocr'));continue
    for page in packet['pages']:
     for offset,excerpt in legacy.chunks(page['text']):
      if len(candidates)>=legacy.MAX_CHUNKS:bounded=True;break
      candidates.append(dict(citation=f'D{doc.id}:P{page["number"]}:{offset}',project_id=pid,kind='document',
       dataset_id=doc.id,title=doc.filename,source=doc.filename+' · página '+str(page['number']),url=None,
       excerpt=excerpt,offset=offset,page=page['number'],record_type='pdf_page',
       pdf_origin=dict(filename=doc.filename,sha256=doc.sha256,page=page['number'],pages=packet['page_count'],
        text_dataset_id=packet['text_dataset_id'],text_sha256=packet['text_sha256'],ocr_used=False),
       content_sha256=digest(dict(source_sha256=doc.sha256,page=page['number'],offset=offset,excerpt=excerpt))))
     if len(candidates)>=legacy.MAX_CHUNKS:break
    if any(len(p['text'])>legacy.MAX_DOCUMENT_CHARS for p in packet['pages']):bounded=True
    for number in packet['empty_pages']:skipped.append(dict(dataset_id=doc.id,page=number,reason='pdf_page_without_text'))
    continue
   if doc.detail.startswith(CONTRACT+'\n'):
    verified=workbook_rows(session,pid,doc,uploads)
    if not verified:skipped.append(dict(dataset_id=doc.id,reason='workbook_integrity_or_selection_error'));continue
    source,meta,records=verified
    available.append(dict(source_dataset_id=source.id,text_dataset_id=doc.id,sheet=meta['sheet'],columns=meta['columns'],rows=len(records)))
    for row in records:
     idcell=next((c for c in row['cells'] if section_header(c['label'])),None)
     if target is not None and (not idcell or section_value(idcell['value'])!=target):continue
     if len(candidates)>=legacy.MAX_CHUNKS:bounded=True;break
     citation=row_citation(pid,doc,source,meta,row)
     citation['_exact_section']=target is not None;candidates.append(citation)
    continue
   if Path(doc.filename).suffix.lower() not in legacy.TEXT_EXTENSIONS:
    skipped.append(dict(dataset_id=doc.id,reason='extraction_not_implemented'));continue
   raw,error=legacy.document_bytes(session,doc,uploads)
   if error:skipped.append(dict(dataset_id=doc.id,reason=error));continue
   try:
    text=raw.decode('utf-8-sig')
    if Path(doc.filename).suffix.lower()=='.csv':
     text='\n'.join(' | '.join(row[:30]) for _,row in zip(range(500),legacy.csv.reader(legacy.io.StringIO(text))));bounded=True
   except (UnicodeError,legacy.csv.Error):skipped.append(dict(dataset_id=doc.id,reason='invalid_text'));continue
   bounded=bounded or len(text)>legacy.MAX_DOCUMENT_CHARS
   for offset,excerpt in legacy.chunks(text):
    if len(candidates)>=legacy.MAX_CHUNKS:bounded=True;break
    candidates.append(dict(citation=f'D{doc.id}:{offset}',project_id=pid,kind='document',dataset_id=doc.id,title=doc.filename,
     source='Archivo del proyecto',url=None,excerpt=excerpt,offset=offset,content_sha256=hashlib.sha256(excerpt.encode()).hexdigest()))
 ids={e['source_dataset_id'] for e in available}
 for s in skipped:
  if s['dataset_id'] in ids:s['reason']='original_preserved_selected_columns_available'
 ranked=[]
 for index,entry in enumerate(candidates):
  exact=entry.pop('_exact_section',False);body=legacy.normalized(entry['excerpt']);title=legacy.normalized(entry['title'])
  if target is not None and entry.get('record_type')!='workbook_row':
   if not re.search(r'\bseccion(?:\s+electoral)?\s*[:#.-]?\s*0*'+str(target)+r'\b',body+' '+title):continue
  body_words=word_counts(body);title_words=word_counts(title)
  if not exact and not all(t in body_words or t in title_words for t in wanted):continue
  score=10000 if exact else sum((3 if t in title_words else 0)+min(body_words[t],5) for t in wanted)
  if score:ranked.append((score,index,entry))
 ranked.sort(key=lambda t:(-t[0],t[1]));selected=[];used=0
 for score,_,entry in ranked[:limit]:
  if used+len(entry['excerpt'])>legacy.CONTEXT_CHARS:bounded=True;break
  selected.append(dict(entry,relevance_score=score));used+=len(entry['excerpt'])
 return dict(mode='local_lexical_evidence',project_id=pid,question=question,answer=None,ai_used=False,external_calls=0,citations=selected,
  coverage=dict(news_scanned=news_scanned,documents_scanned=documents_scanned,maximum_news=legacy.MAX_NEWS,maximum_documents=legacy.MAX_DOCUMENTS,
   bounded=bounded or len(ranked)>len(selected),not_indexed=skipped,workbook_extractions=available),
  exact_section_query=target,document_id=document_id,source_kind=source_kind,note='Evidencia documental del proyecto con referencias a páginas o celdas de origen.')
