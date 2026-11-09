"""Workbook extraction, unchanged originals, cell provenance and project isolation."""
from io import BytesIO
from pathlib import Path
import hashlib,json,zipfile
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from app.models import Dataset,DatasetBlob,SectionMetric,AuditEvent
from app.workbook_evidence import read_workbook,prepare,WorkbookInvalid
from app.workbook_api import WorkbookSelection,WorkbookExtract,annotate_context
from app.workspace_api import ContextRequest
from app.knowledge import retrieve_context
from test_manual_reviews import archive,endpoint

N='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
def book(*,rows=None,extra=None,sheet_hidden=False,relationships=''):
 rows=rows or '<row r="1"><c r="A1" t="inlineStr"><is><t>Sección</t></is></c><c r="B1" t="inlineStr"><is><t>Lista nominal</t></is></c></row><row r="2"><c r="A2"><v>158</v></c><c r="B2"><v>0</v></c></row>'
 parts={'[Content_Types].xml':'<Types/>','xl/workbook.xml':f'<workbook xmlns="{N}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Datos" sheetId="1" r:id="r1"'+(' state="hidden"' if sheet_hidden else '')+'/></sheets></workbook>',
 'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Target="worksheets/sheet1.xml"/>'+relationships+'</Relationships>',
 'xl/worksheets/sheet1.xml':f'<worksheet xmlns="{N}"><sheetData>{rows}</sheetData></worksheet>'}
 parts.update(extra or {});b=BytesIO()
 with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
  for n,raw in parts.items():z.writestr(n,raw)
 return b.getvalue()
def add(a,raw=None,*,pid=None,path='database',filename='Fixture.xlsx'):
 raw=book() if raw is None else raw
 r=Dataset(project_id=pid or a[2].id,uploaded_by=a[4][0].id,filename=filename,media_type='.xlsx',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),path=path,detail='Original fixture')
 a[1].add(r);a[1].flush()
 if path=='database':a[1].add(DatasetBlob(project_id=r.project_id,dataset_id=r.id,content=raw))
 a[1].commit();return r
def choose(**kw):return WorkbookSelection(sheet='Datos',columns=['A','B'],source_year=2024,**kw)
def call(a,did=None,suffix='',*,body=None,user=0,pid=None):
 path='/api/projects/{pid}/library/workbooks'+('/{dataset_id}' if did else '')+suffix
 return endpoint(a[0],path,'POST' if body else 'GET')(pid=pid or a[2].id,user=a[4][user],session=a[1],**({'dataset_id':did} if did else {}),**({'body':body} if body else {}))
def save(a,r,selection=None,*,user=0):
 body=selection or choose();p=call(a,r.id,'/preview',body=body)
 return call(a,r.id,'/extract',body=WorkbookExtract(**body.model_dump(),preview_sha256=p['preview_sha256']),user=user)

def test_literal_rows_have_cells_headers_and_zero_not_missing():
 p=prepare(book(),'Fixture.xlsx',choose());assert p['metadata']['row_count']==1
 assert 'Lista nominal [B2]: 0' in p['text'] and 'Sección [A2]: 158' in p['text']
 assert p['preview'][0]['location']=='Datos!A2,B2' and p['preview'][0]['cells'][1]['value']=='0'

def test_selection_does_not_index_other_columns():
 p=prepare(book(),'Fixture.xlsx',WorkbookSelection(sheet='Datos',columns=['A']))
 assert 'Lista nominal' not in p['text'] and 'B2' not in p['text']

def test_formula_cached_value_is_read_without_executing_formula():
 raw=book(rows='<row r="1"><c r="A1" t="inlineStr"><is><t>Valor</t></is></c></row><row r="2"><c r="A2"><f>WEBSERVICE("https://never.test")</f><v>7</v></c></row>')
 p=prepare(raw,'Fixture.xlsx',WorkbookSelection(sheet='Datos',columns=['A']))
 assert 'WEBSERVICE' not in p['text'] and 'Valor [A2]: 7' in p['text']

def test_formula_without_cache_is_not_zero():
 raw=book(rows='<row r="1"><c r="A1" t="inlineStr"><is><t>Valor</t></is></c></row><row r="2"><c r="A2"><f>1+2</f></c></row>')
 p=prepare(raw,'Fixture.xlsx',WorkbookSelection(sheet='Datos',columns=['A']))
 assert '[Fórmula sin valor guardado]' in p['text']

@pytest.mark.parametrize('extra',[{'xl/vbaProject.bin':b'blocked'},{'xl/externalLinks/a.xml':'<a/>'},{'../bad.xml':'<a/>'},{'xl/embeddings/a.bin':b'blocked'}])
def test_active_content_and_unsafe_paths_are_rejected(extra):
 with pytest.raises(WorkbookInvalid):read_workbook(book(extra=extra))

def test_external_relationship_is_never_followed():
 with pytest.raises(WorkbookInvalid):read_workbook(book(relationships='<Relationship Id="external" Target="https://never.test" TargetMode="External"/>'))

def test_hidden_rows_are_not_read():
 raw=book(rows='<row r="1"><c r="A1" t="inlineStr"><is><t>Dato</t></is></c></row><row r="2" hidden="1"><c r="A2" t="inlineStr"><is><t>HIDDEN</t></is></c></row><row r="3"><c r="A3"><v>3</v></c></row>')
 p=prepare(raw,'Fixture.xlsx',WorkbookSelection(sheet='Datos',columns=['A']));assert 'HIDDEN' not in p['text'] and p['metadata']['row_count']==1

def test_hidden_only_workbook_is_rejected():
 with pytest.raises(WorkbookInvalid):read_workbook(book(sheet_hidden=True))

@pytest.mark.parametrize('raw',[b'not a workbook',book(extra={'xl/sharedStrings.xml':'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///never">]><sst>&e;</sst>'})])
def test_invalid_zip_or_xml_entities_are_rejected_without_source_echo(raw):
 with pytest.raises(WorkbookInvalid) as e:read_workbook(raw)
 assert 'file://' not in str(e.value)

def test_missing_or_repeated_column_selection_rejected():
 for columns in [['C'],['A','A']]:
  with pytest.raises(WorkbookInvalid):prepare(book(),'Fixture.xlsx',WorkbookSelection(sheet='Datos',columns=columns))

def test_no_data_in_range_rejected():
 with pytest.raises(WorkbookInvalid):prepare(book(),'Fixture.xlsx',choose(first_row=3))

def test_source_date_and_origin_are_declared_not_inferred():
 p=prepare(book(),'Fixture.xlsx',choose(source_note='Aportado por proyecto'))
 assert 'Año declarado: 2024' in p['text'] and 'Procedencia declarada: Aportado por proyecto' in p['text']

def test_extraction_deduplicates_and_keeps_original_and_history(archive):
 r=add(archive);original=(r.sha256,r.detail,r.size_bytes);count=archive[1].scalar(select(func.count()).select_from(SectionMetric))
 first=save(archive,r);second=save(archive,r)
 assert not first['deduplicated'] and second['deduplicated'] and first['dataset_id']==second['dataset_id']
 archive[1].refresh(r);assert (r.sha256,r.detail,r.size_bytes)==original
 assert archive[1].scalar(select(func.count()).select_from(Dataset))==2
 assert archive[1].scalar(select(func.count()).select_from(SectionMetric))==count

def test_search_context_contains_cell_references_and_origin(archive):
 r=add(archive);save(archive,r);p=endpoint(archive[0],'/api/projects/{pid}/knowledge/context','POST')(
  pid=archive[2].id,body=ContextRequest(question='Sección 158',source_kind='documents'),user=archive[4][2],session=archive[1])
 assert p['citations'] and p['citations'][0]['title']=='Sección 158' and 'Sección: 158' in p['citations'][0]['excerpt']
 assert p['citations'][0]['workbook_origin']['source_year_declared']==2024
 assert p['coverage']['not_indexed'][0]['reason']=='original_preserved_selected_columns_available'

def test_changed_selection_requires_new_preview(archive):
 r=add(archive);p=call(archive,r.id,'/preview',body=choose())
 with pytest.raises(HTTPException) as e:call(archive,r.id,'/extract',body=WorkbookExtract(**choose(source_note='Changed').model_dump(),preview_sha256=p['preview_sha256']))
 assert e.value.status_code==409 and archive[1].scalar(select(func.count()).select_from(Dataset))==1

def test_changed_source_bytes_fail_integrity_before_preview(archive):
 r=add(archive);blob=archive[1].get(DatasetBlob,r.id);blob.content=b'changed';archive[1].commit()
 with pytest.raises(HTTPException) as e:call(archive,r.id,'/preview',body=choose())
 assert e.value.status_code==409

@pytest.mark.parametrize('suffix',['','/preview','/extract'])
def test_foreign_source_id_cannot_be_read_or_extracted(archive,suffix):
 r=add(archive,pid=archive[3].id)
 body=WorkbookExtract(**choose().model_dump(),preview_sha256='0'*64) if suffix=='/extract' else choose() if suffix else None
 with pytest.raises(HTTPException) as e:call(archive,r.id,suffix,body=body)
 assert e.value.status_code==404

def test_reader_can_inspect_but_not_extract(archive):
 r=add(archive);assert call(archive,r.id,user=2)['sheets']
 with pytest.raises(HTTPException) as e:save(archive,r,user=2)
 assert e.value.status_code==403

def test_consultant_can_prepare_own_project_evidence(archive):
 r=add(archive);assert save(archive,r,user=1)['rows']==1

def test_unsafe_filesystem_source_path_cannot_be_read(archive,tmp_path):
 path=tmp_path/'outside.xlsx';raw=book();path.write_bytes(raw);r=add(archive,raw,path=str(path))
 with pytest.raises(HTTPException) as e:call(archive,r.id)
 assert e.value.status_code==409 and str(path) not in e.value.detail

def test_unrelated_project_evidence_is_not_annotated(archive):
 r=add(archive);save(archive,r)
 p=retrieve_context(archive[1],archive[3].id,'Sección',Path(archive[0].state.engine.url.database).parent/'uploads',source_kind='documents')
 p=annotate_context(archive[1],archive[3].id,p,Path('unused'));assert not p['citations'] and p['coverage']['workbook_extractions']==[]

def test_outbound_calls_are_not_used_even_with_tokens(archive,monkeypatch):
 import socket
 def fail(*a,**kw):raise AssertionError('Outbound call')
 monkeypatch.setattr(socket,'getaddrinfo',fail);monkeypatch.setattr(socket,'create_connection',fail);monkeypatch.setenv('APIFY_TOKEN','not-used')
 r=add(archive);assert save(archive,r)['external_calls']==0

def test_resource_bounds_are_enforced(monkeypatch):
 import app.workbook_evidence as parser
 monkeypatch.setattr(parser,'MAX_CELLS',1)
 with pytest.raises(WorkbookInvalid):read_workbook(book())

def test_corrupted_original_is_not_reported_as_verified_extraction(archive):
 r=add(archive);save(archive,r);archive[1].get(DatasetBlob,r.id).content=b'corrupt';archive[1].commit()
 uploads=Path(archive[0].state.engine.url.database).parent/'uploads'
 p=annotate_context(archive[1],archive[2].id,retrieve_context(archive[1],archive[2].id,'Sección',uploads),uploads)
 assert p['coverage']['workbook_extractions']==[] and all('workbook_origin' not in c for c in p['citations'])

def test_extraction_quota_rejects_before_creating_text(archive):
 from datetime import datetime,timezone
 from app.models import UsageCounter
 r=add(archive);archive[1].add(UsageCounter(project_id=archive[2].id,action='library.xlsx.extract',bucket=datetime.now(timezone.utc).strftime('%Y-%m-%d'),used=20));archive[1].commit()
 with pytest.raises(HTTPException) as e:save(archive,r)
 assert e.value.status_code==429 and archive[1].scalar(select(func.count()).select_from(Dataset))==1
