"""Readable report exports, visible metadata and permission-preserving archive."""
import json,hashlib
from html.parser import HTMLParser
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from app.models import ReportVersion,Report,AuditEvent
from app.pulse_models import PlatformBrand
from app.report_document import render_document
from test_manual_reviews import archive
from test_reports import create,revise,release,call,detail
from test_explorer import save as save_selection

def document(a,rid,version=1,*,actor=0,pid=None):
    return call(a,'/{report_id}/versions/{version}/document',report_id=rid,version=version,actor=actor,pid=pid)

def test_writer_archive_states_and_types_do_not_change_sources(archive):
    rid=create(archive)['id'];p=call(archive);assert p['items'][0]['state']=='draft' and p['items'][0]['origin']=='documentary'
    release(archive,rid);assert call(archive)['items'][0]['state']=='released'
    revise(archive,rid);assert call(archive)['items'][0]['state']=='updated' and call(archive)['items'][0]['published_version']==1
    viewer=call(archive,actor=2)['items'][0];assert viewer['state']=='released' and viewer['version']==1 and viewer['title']=='Informe documental'

def test_selection_origin_metadata_and_frozen_document_export(archive):
    r=save_selection(archive,[f'news:{archive[5][0].id}']);assert call(archive)['items'][0]['origin']=='selection'
    d=json.loads(document(archive,r['id']).body);assert 'Selección de evidencias' in d['html'] and d['sha256']==detail(archive,r['id'])['sha256']

def test_document_is_stored_version_not_a_new_search(archive):
    rid=create(archive,note='Primera nota')['id'];before=json.loads(document(archive,rid).body)
    archive[5][0].abstract='Changed after save';archive[1].commit();revise(archive,rid,note='Segunda nota')
    old=json.loads(document(archive,rid).body);assert old==before and 'Changed after save' not in old['html']
    assert 'Segunda nota' in json.loads(document(archive,rid,2).body)['html']

def test_unreleased_and_foreign_documents_are_hidden(archive):
    rid=create(archive)['id']
    for actor in [2,3]:
        with pytest.raises(HTTPException) as e:document(archive,rid,actor=actor)
        assert e.value.status_code==404
    with pytest.raises(HTTPException) as e:document(archive,rid,pid=archive[3].id,actor=3)
    assert e.value.status_code==404

def test_reader_downloads_only_released_version(archive):
    rid=create(archive)['id'];release(archive,rid);revise(archive,rid,note='Hidden next draft')
    allowed=json.loads(document(archive,rid,actor=2).body);assert 'Hidden next draft' not in allowed['html']
    with pytest.raises(HTTPException) as e:document(archive,rid,2,actor=2)
    assert e.value.status_code==404

def test_old_released_version_retains_its_actual_release_status(archive):
    rid=create(archive)['id'];release(archive,rid);revise(archive,rid);release(archive,rid,2)
    old=call(archive,'/{report_id}/versions/{version}',report_id=rid,version=1);assert old['is_released'] and old['published_version']==2
    assert 'Habilitada para lectores del proyecto' in json.loads(document(archive,rid).body)['html']

def test_brand_and_project_are_dynamic_and_escaped(archive):
    archive[1].add(PlatformBrand(id=1,name='Marca <script>custom</script>',tagline=''))
    archive[2].name='Proyecto <img src=x>';archive[1].commit();rid=create(archive)['id']
    html=json.loads(document(archive,rid).body)['html'];assert 'Marca &lt;script&gt;custom&lt;/script&gt;' in html and 'Proyecto &lt;img src=x&gt;' in html

class Tags(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        if tag=='a':self.links.append(dict(attrs).get('href'))

@pytest.mark.parametrize('url',['javascript:alert(1)','data:text/html,private','https://user:secret@example.org/path','https://[bad','file:///private'])
def test_untrusted_document_text_and_links_cannot_create_active_content(url):
    report=dict(id=1,version=1,published_version=None,sha256='fixture',created_at='fixture',snapshot=dict(title='</title><script>x</script>',editorial_note='<img src=x onerror=alert(1)>',scope='<iframe>bad</iframe>',context=dict(citations=[dict(citation='N1',title='<svg/onload=x>',source='Literal & source',url=url,excerpt='<script>fetch("private")</script>',content_sha256='fixture')])))
    html=render_document(report,brand='NEXO',project='Fixture');parsed=Tags();parsed.feed(html)
    assert not {'script','img','iframe','svg','form','object','embed'}.intersection(parsed.tags) and parsed.links==[]
    assert '&lt;script&gt;' in html and "default-src 'none'" in html and '@media print' in html

def test_document_headers_and_get_requests_do_not_write(archive):
    rid=create(archive)['id'];before=archive[1].scalar(select(func.count()).select_from(AuditEvent));response=document(archive,rid)
    assert response.headers['cache-control']=='no-store' and response.headers['x-content-type-options']=='nosniff'
    assert archive[1].scalar(select(func.count()).select_from(AuditEvent))==before
    body=json.loads(response.body);assert body['format']=='html' and body['filename'].endswith('_v1.html') and 'no-referrer' in body['html']

def test_tampered_snapshot_cannot_be_exported_as_document(archive):
    rid=create(archive)['id'];row=archive[1].scalar(select(ReportVersion));row.payload=row.payload+' ';archive[1].commit()
    with pytest.raises(HTTPException) as e:document(archive,rid)
    assert e.value.status_code==409

def test_printed_briefing_preserves_known_and_unknown_saved_analytics():
    r=dict(version=1,published_version=None,created_at='fixture',sha256='fixture',snapshot=dict(mode='local_documentary_briefing_v1',title='Briefing',context=dict(citations=[]),briefing=dict(filters=dict(start='begin',end='end'),news_count=5,pulse=dict(metrics=dict(mentions=10),active_alerts=None),content_analytics=dict(pieces=5,tone_classified=3,mood_index=25,mockery_percentage=None,tone=[dict(label='positive',percentage=25)],emotions=[dict(emotion='fear',percentage=50),dict(emotion='joy',percentage=None)]))))
    html=render_document(r,brand='Brand',project='Project')
    assert 'Positivo: 25 %' in html and 'Miedo: 50 %' in html and 'Alegría: — %' in html and 'Señales activadas: —' in html
