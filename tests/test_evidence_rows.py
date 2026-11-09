"""Regression for mixed-section chunks and technical metadata in user results."""
from pathlib import Path
import pytest,json
from sqlalchemy import select
from app.models import DatasetBlob
from app.evidence_search import retrieve_context
from app.workbook_api import WorkbookSelection
from app.report_api import ReportInput
from app.workspace_api import ContextRequest
from test_manual_reviews import archive,endpoint
from test_workbook_evidence import book,add,save
from test_reports import detail

def fixture(a):
 rows='<row r="1"><c r="A1" t="inlineStr"><is><t>SECCION 736</t></is></c><c r="B1" t="inlineStr"><is><t>LISTA NOMINAL</t></is></c></row>'
 for n,section,count in [(2,158,438),(3,211,158),(4,1580,999)]:
  rows+=f'<row r="{n}"><c r="A{n}"><v>{section}</v></c><c r="B{n}"><v>{count}</v></c></row>'
 r=add(a,book(rows=rows));save(a,r);return r
def query(a,q,*,pid=None,**kw):
 return retrieve_context(a[1],pid or a[2].id,q,Path(a[0].state.engine.url.database).parent/'uploads',source_kind='documents',**kw)

@pytest.mark.parametrize('q',['SECCION 158','sección 158','158','seccion:158','lista nominal de la sección 158','¿Cuál es la lista nominal de la sección 158?'])
def test_exact_section_returns_only_requested_row(archive,q):
 fixture(archive);p=query(archive,q);assert len(p['citations'])==1
 c=p['citations'][0];assert c['title']=='Sección 158' and c['workbook_origin']['row']==2
 assert c['excerpt']=='Sección: 158\nLista nominal: 438'
 assert '211' not in c['excerpt'] and '1580' not in c['excerpt']

@pytest.mark.parametrize('q',['seccion 15','seccion 736','seccion 999'])
def test_no_match_is_not_substituted_by_other_rows_or_header_numbers(archive,q):
 fixture(archive);assert query(archive,q)['citations']==[]

def test_value_in_other_column_does_not_become_section_identifier(archive):
 fixture(archive);p=query(archive,'seccion 211');assert len(p['citations'])==1
 assert p['citations'][0]['display_fields'][1]['value']=='158' and p['citations'][0]['workbook_origin']['row']==3

def test_metadata_banner_is_not_part_of_the_excerpt(archive):
 fixture(archive);c=query(archive,'seccion 158')['citations'][0]
 assert not any(x in c['excerpt'] for x in ['SHA256','Encabezados','Archivo de origen','SECCION 736'])
 assert c['display_fields'][0]['original_label']=='SECCION 736'
 assert c['workbook_origin']['cells']==['A2','B2'] and len(c['workbook_origin']['sha256'])==64

def test_generic_field_query_keeps_rows_separate_and_respects_limit(archive):
 fixture(archive);p=query(archive,'lista nominal',limit=2)
 assert len(p['citations'])==2 and p['coverage']['bounded']
 assert len({c['workbook_origin']['row'] for c in p['citations']})==2

def test_structured_queries_require_all_search_words_when_no_id_requested(archive):
 fixture(archive);assert query(archive,'lista inexistente')['citations']==[]

def test_corrupt_source_is_not_returned_as_a_raw_sidecar_fallback(archive):
 r=fixture(archive);archive[1].get(DatasetBlob,r.id).content=b'corrupted';archive[1].commit()
 p=query(archive,'seccion 158');assert p['citations']==[]
 assert any(c['reason']=='workbook_integrity_or_selection_error' for c in p['coverage']['not_indexed'])

def test_other_project_cannot_retrieve_workbook_rows(archive):
 fixture(archive);assert query(archive,'seccion 158',pid=archive[3].id)['citations']==[]

def test_context_route_uses_row_search_and_same_authorization(archive):
 fixture(archive);route=endpoint(archive[0],'/api/projects/{pid}/knowledge/context','POST')
 p=route(pid=archive[2].id,body=ContextRequest(question='seccion 158'),user=archive[4][2],session=archive[1])
 assert len(p['citations'])==1 and p['citations'][0]['record_type']=='workbook_row'

def test_documentary_digest_quotes_one_row(archive):
 fixture(archive);route=endpoint(archive[0],'/api/projects/{pid}/knowledge/critical-audit','POST')
 p=route(pid=archive[2].id,body=ContextRequest(question='seccion 158'),user=archive[4][1],session=archive[1])
 assert len(p['citations'])==1 and 'SHA256' not in p['citations'][0]['excerpt'] and not p['ai_used']

def test_new_report_freezes_same_readable_row_and_cell_provenance(archive):
 fixture(archive);route=endpoint(archive[0],'/api/projects/{pid}/reports','POST')
 made=route(pid=archive[2].id,body=ReportInput(title='Ficha sección',question='seccion 158',source_kind='documents'),user=archive[4][1],session=archive[1])
 saved=detail(archive,made['id'])['snapshot']['context']['citations']
 assert len(saved)==1 and saved[0]['title']=='Sección 158' and saved[0]['workbook_origin']['row']==2
 assert 'Archivo de origen' not in saved[0]['excerpt']

def test_preview_stays_limited_and_does_not_expose_internal_record_array(archive):
 r=fixture(archive);route=endpoint(archive[0],'/api/projects/{pid}/library/workbooks/{dataset_id}/preview','POST')
 p=route(pid=archive[2].id,dataset_id=r.id,body=WorkbookSelection(sheet='Datos',columns=['A','B']),user=archive[4][1],session=archive[1])
 assert set(p)=={'metadata','preview_sha256','preview'}
