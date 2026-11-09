"""Explicit human piece-level coding; source changes require another review."""
import hashlib,json
from datetime import datetime,timezone
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,update,func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .apify_port import Strict,Sentiment,Emotion
from .models import NewsArticle,AuditEvent
from .pulse_models import PulseDocument
from .delivery_models import ContentAssessment
from .analysis_models import ContentAnalysis
from .pulse_service import window

class AssessmentInput(Strict):
    sentiment:Sentiment|None=None
    emotion:Emotion|None=None
    mockery:bool|None=None
    expected_version:int=Field(ge=0)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')

def source_values(row):
    return dict(source_title=row.title,source_body=row.abstract if isinstance(row,NewsArticle) else row.text,source_url=row.url)

def fingerprint(values):return hashlib.sha256(json.dumps(values,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def install_assessment_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/briefing/assessments')
    def listing(pid:int,start:datetime|None=None,end:datetime|None=None,source_kind:str='all',user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'});start,end=window(start,end)
        if source_kind not in {'all','news','pulse'}:raise HTTPException(422,'Tipo de fuente no admitido.')
        result=[];bounded=False
        for kind,model,stamp,target in [('news',NewsArticle,func.coalesce(NewsArticle.published_at,NewsArticle.ingested_at),'news_id'),('pulse',PulseDocument,PulseDocument.published_at,'pulse_document_id')]:
            if source_kind!='all' and kind!=source_kind:continue
            query=select(model).where(model.project_id==pid,stamp>=start,stamp<end)
            if kind=='pulse':query=query.where(PulseDocument.is_demo.is_(False))
            rows=session.scalars(query.order_by(stamp.desc(),model.id.desc()).limit(101)).all();bounded=bounded or len(rows)>100
            ids=[r.id for r in rows[:100]]
            labels={getattr(r,target):r for r in session.scalars(select(ContentAssessment).where(ContentAssessment.project_id==pid,getattr(ContentAssessment,target).in_(ids))).all()}
            automatic={(getattr(r,target),r.source_sha256):r for r in session.scalars(select(ContentAnalysis).where(ContentAnalysis.project_id==pid,
                getattr(ContentAnalysis,target).in_(ids),ContentAnalysis.state=='completed',ContentAnalysis.contract_version=='content-v1').order_by(ContentAnalysis.id)).all()}
            for row in rows[:100]:
                values=source_values(row);sha=fingerprint(values);label=labels.get(row.id);valid=bool(label and label.source_sha256==sha)
                ai=automatic.get((row.id,sha));ai_valid=bool(ai)
                chosen=label if valid else ai if ai_valid else None
                result.append(dict(kind=kind,id=row.id,title=row.title,url=row.url,excerpt=values['source_body'][:320],
                    source_sha256=sha,expected_version=label.version if label else 0,stale=bool(label and not valid),
                    origin='correction' if valid else 'ai' if ai_valid else 'pending',
                    sentiment=chosen.sentiment if chosen else None,emotion=chosen.emotion if chosen else None,mockery=chosen.mockery if chosen else None))
        return dict(items=result[:100],truncated=bounded or len(result)>100,limit=100)

    @app.put('/api/projects/{pid}/briefing/assessments/{kind}/{source_id}')
    def classify(pid:int,kind:Literal['news','pulse'],source_id:int,body:AssessmentInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        if kind not in {'news','pulse'}:raise HTTPException(422,'Tipo de fuente no admitido.')
        model=NewsArticle if kind=='news' else PulseDocument
        query=select(model).where(model.id==source_id,model.project_id==pid)
        if kind=='pulse':query=query.where(PulseDocument.is_demo.is_(False))
        source=session.scalar(query)
        if source is None:raise HTTPException(404,'Fuente no disponible.')
        values=source_values(source);sha=fingerprint(values)
        if sha!=body.source_sha256:raise HTTPException(409,'La fuente cambió. Vuelve a abrirla antes de clasificar.')
        if len(values['source_body'].encode())>32768:raise HTTPException(422,'La fuente excede el tamaño de revisión de esta entrega.')
        target='news_id' if kind=='news' else 'pulse_document_id'
        fields=dict(**values,source_sha256=sha,sentiment=body.sentiment,emotion=body.emotion,mockery=body.mockery,
            reviewed_by=user.id,version=body.expected_version+1,updated_at=datetime.now(timezone.utc))
        try:
            if not body.expected_version:session.add(ContentAssessment(project_id=pid,is_demo=False,**{target:source_id},**fields))
            else:
                changed=session.execute(update(ContentAssessment).where(ContentAssessment.project_id==pid,getattr(ContentAssessment,target)==source_id,
                    ContentAssessment.version==body.expected_version).values(**fields),execution_options={'synchronize_session':False})
                if changed.rowcount!=1:session.rollback();raise HTTPException(409,'Otra persona cambió esta revisión. Recarga la lista.')
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='briefing.assess',target=f'{kind}:{source_id}:v{body.expected_version+1}'))
            session.commit();session.expire_all();return dict(version=body.expected_version+1)
        except IntegrityError:session.rollback();raise HTTPException(409,'La revisión ya existe o cambió. Recarga la lista.') from None
