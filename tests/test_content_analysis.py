"""Only fabricated source text and fabricated model output; no provider call."""
from datetime import timedelta,datetime,timezone
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from app.models import NewsArticle
from app.analysis_models import ContentAnalysis
from app.content_analysis import prepare,process_one,status,AnalysisUnavailable,AnalysisOutput,INSTRUCTIONS
from app.analysis_api import AnalysisCut
from test_manual_reviews import archive,endpoint
from test_briefing import ready,preview,save,NOW
from test_delivery import assess,add_news

class FakeModel:
    provider='synthetic-test-only'
    model='fabricated-output-v1'
    def __init__(self,**changes):self.changes=changes;self.calls=0
    def analyze(self,**kwargs):
        self.calls+=1;self.request=kwargs
        return dict(sentiment='positive',emotion='joy',mockery=False,confidence=.95,evidence='Cobertura documental',**self.changes)

def queue(a):
    ready(a);result=prepare(a[1],a[2].id,NOW-timedelta(days=1),NOW);a[1].commit()
    return result,a[1].scalar(select(ContentAnalysis).where(ContentAnalysis.project_id==a[2].id).order_by(ContentAnalysis.id.desc()))

def run(a,row,port):return process_one(a[1],a[2].id,row.id,port)

def test_discovery_is_project_scoped_and_idempotent(archive):
    result,row=queue(archive);assert result['queued']==1 and result['external_calls']==0
    assert queue(archive)[0]['queued']==0 and row.news_id==archive[-1][0].id
    s=status(archive[1],archive[2].id,NOW-timedelta(days=1),NOW);assert s['counts']['queued']==1 and not s['automatic_analysis_connected']

def test_disconnected_port_never_consumes_attempt_or_reads_credentials(archive,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-unused');_,row=queue(archive)
    with pytest.raises(AnalysisUnavailable):process_one(archive[1],archive[2].id,row.id)
    assert row.attempts==0 and row.state=='queued' and preview(archive)['content_analytics']['tone_classified']==0

def test_validated_model_output_flows_to_briefing_and_frozen_report(archive):
    _,row=queue(archive);model=FakeModel();assert run(archive,row,model)=='completed'
    assert model.request['max_output_tokens']==600 and model.request['timeout_seconds']==20
    p=preview(archive);assert p['ai_used'] and p['content_analytics']['tone_classified']==1
    assert p['content_analytics']['ai_provenance'][0]['model']=='fabricated-output-v1'
    assert p['content_analytics']['mockery_classified']==1 and p['content_analytics']['emotions'][0]['count']==1
    assert save(archive,p)['version']==1
    assert run(archive,row,model)=='completed' and model.calls==1

def test_manual_correction_has_priority_and_does_not_destroy_model_provenance(archive):
    _,row=queue(archive);run(archive,row,FakeModel());assess(archive,sentiment='negative',emotion='anger',mockery=True)
    p=preview(archive);assert p['content_analytics']['tone'][2]['count']==1 and not p['ai_used']
    assert row.sentiment=='positive' and row.provider=='synthetic-test-only'

def test_optional_review_opens_with_current_ai_labels(archive):
    _,row=queue(archive);run(archive,row,FakeModel())
    result=endpoint(archive[0],'/api/projects/{pid}/briefing/assessments')(pid=archive[2].id,start=NOW-timedelta(days=1),
        end=NOW,source_kind='all',user=archive[4][0],session=archive[1])
    assert result['items'][0]['origin']=='ai' and result['items'][0]['sentiment']=='positive'
    assert result['items'][0]['expected_version']==0

def test_real_pulse_source_can_receive_ai_analysis_without_demo_or_foreign_content(archive):
    from test_pulse import add_actor,ingest,post
    from app.pulse_models import PulseDocument
    ready(archive);actor=add_actor(archive)['id'];ingest(archive,[post(actor,text='Cobertura documental')])
    result,_=queue(archive);assert result['queued']==2
    row=archive[1].scalar(select(ContentAnalysis).where(ContentAnalysis.pulse_document_id.is_not(None)))
    assert row and run(archive,row,FakeModel())=='completed'
    assert preview(archive)['content_analytics']['ai_analyzed_pieces']==1

def test_abstention_does_not_produce_artificial_neutral_score(archive):
    _,row=queue(archive);model=FakeModel();model.analyze=lambda **kw:dict(sentiment=None,emotion=None,mockery=None,confidence=.99,evidence='')
    assert run(archive,row,model)=='needs_review' and preview(archive)['content_analytics']['tone_classified']==0

@pytest.mark.parametrize('changed',[dict(confidence=.79),dict(confidence=.1)])
def test_low_confidence_never_becomes_measured_labels(archive,changed):
    _,row=queue(archive)
    model=FakeModel();original=model.analyze
    model.analyze=lambda **kw:{**original(**kw),**changed}
    assert run(archive,row,model)=='needs_review'
    assert preview(archive)['content_analytics']['tone_classified']==0

@pytest.mark.parametrize('change',[{'sentiment':'invented'},{'mockery':'true'},{'extra':'untrusted'},
    {'confidence':float('nan')},{'evidence':'A quote absent from source'},{'evidence':''}])
def test_invalid_outputs_fail_closed_without_sensitive_errors(archive,change):
    _,row=queue(archive);model=FakeModel();original=model.analyze;model.analyze=lambda **kw:{**original(**kw),**change}
    assert run(archive,row,model)=='failed' and row.error_code=='invalid_or_failed_output'
    assert row.sentiment is None and preview(archive)['content_analytics']['tone_classified']==0

def test_provider_failure_never_stores_exception_text(archive):
    _,row=queue(archive);model=FakeModel()
    def fail(**kwargs):raise RuntimeError('SYNTHETIC_SECRET_MUST_NOT_PERSIST')
    model.analyze=fail;assert run(archive,row,model)=='failed' and row.evidence is None
    assert row.error_code=='invalid_or_failed_output'

def test_changed_source_invalidates_results_and_queues_new_revision(archive):
    _,row=queue(archive);run(archive,row,FakeModel());archive[-1][0].abstract='Contenido corregido';archive[1].commit()
    assert preview(archive)['content_analytics']['tone_classified']==0
    result,new=queue(archive);assert result['queued']==1 and new.id!=row.id

def test_stale_source_is_not_sent_to_model(archive):
    _,row=queue(archive);archive[-1][0].abstract='Modificada';archive[1].commit();model=FakeModel()
    assert run(archive,row,model)=='stale' and model.calls==0

def test_source_changed_during_provider_call_is_not_accepted(archive):
    _,row=queue(archive);model=FakeModel();original=model.analyze
    def mutate(**kw):
        archive[-1][0].abstract='Revisión concurrente';archive[1].commit();return original(**kw)
    model.analyze=mutate;assert run(archive,row,model)=='stale'

def test_foreign_job_cannot_be_processed(archive):
    _,row=queue(archive)
    with pytest.raises(ValueError):process_one(archive[1],archive[3].id,row.id,FakeModel())

def test_api_reader_can_read_status_but_not_enqueue(archive):
    ready(archive);args=dict(pid=archive[2].id,user=archive[4][2],session=archive[1])
    get=endpoint(archive[0],'/api/projects/{pid}/briefing/analysis')
    assert get(**args,start=NOW-timedelta(days=1),end=NOW)['counts']['queued']==0
    post=endpoint(archive[0],'/api/projects/{pid}/briefing/analysis/prepare','POST')
    with pytest.raises(HTTPException) as e:post(**args,body=AnalysisCut(start=NOW-timedelta(days=1),end=NOW))
    assert e.value.status_code==403
    args['user']=archive[4][3]
    with pytest.raises(HTTPException) as e:get(**args,start=NOW-timedelta(days=1),end=NOW)
    assert e.value.status_code==404

def test_bounded_discovery_can_progress_past_first_batch(archive):
    ready(archive);add_news(archive,4)
    assert prepare(archive[1],archive[2].id,NOW-timedelta(days=1),NOW,limit=2)['queued']==2
    archive[1].commit()
    assert prepare(archive[1],archive[2].id,NOW-timedelta(days=1),NOW,limit=2)['queued']==2

def test_oversized_source_not_queued_or_sent(archive):
    ready(archive);archive[-1][0].abstract='x'*32769;archive[1].commit()
    assert queue(archive)[0]['oversized']==1

def test_pending_limit_cannot_grow_unbounded(archive,monkeypatch):
    import app.content_analysis as service
    monkeypatch.setattr(service,'MAX_PENDING',1);ready(archive);add_news(archive,2)
    assert queue(archive)[0]['queued']==1 and queue(archive)[0]['bounded']

def test_daily_attempt_budget_blocks_before_model_call(archive,monkeypatch):
    import app.content_analysis as service
    monkeypatch.setattr(service,'MAX_DAILY_ATTEMPTS',0);_,row=queue(archive);model=FakeModel()
    with pytest.raises(AnalysisUnavailable):run(archive,row,model)
    assert model.calls==0 and row.state=='queued'

def test_prompt_keeps_source_untrusted_and_no_voter_belief_inference():
    assert 'untrusted data' in INSTRUCTIONS and 'not instructions' in INSTRUCTIONS
    assert 'political beliefs' in INSTRUCTIONS and 'follow links' in INSTRUCTIONS
