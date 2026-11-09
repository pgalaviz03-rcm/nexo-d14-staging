"""Unique stored URLs, explicit piece labels and declared denominators."""
from sqlalchemy import select,func,case,and_,union_all,literal
from .models import NewsArticle
from .pulse_models import PulseDocument,PulseMention,PulseActor,PulseConfig
from .delivery_models import ContentAssessment
from .analysis_models import ContentAnalysis
from .content_analysis import CONTRACT

def fresh(source):
    body=source.abstract if source is NewsArticle else source.text
    return and_(ContentAssessment.source_title==source.title,ContentAssessment.source_body==body,ContentAssessment.source_url==source.url)

def ai_fresh(source,target,pid):
    body=source.abstract if source is NewsArticle else source.text
    return and_(ContentAnalysis.project_id==pid,getattr(ContentAnalysis,target)==source.id,
        ContentAnalysis.source_title==source.title,ContentAnalysis.source_body==body,ContentAnalysis.source_url==source.url,
        ContentAnalysis.contract_version==CONTRACT,ContentAnalysis.state=='completed')

def label(field,fallback=None):
    # An explicit correction, including abstention/null, takes precedence.
    return case((ContentAssessment.id.is_not(None),getattr(ContentAssessment,field)),
        (ContentAnalysis.id.is_not(None),getattr(ContentAnalysis,field)),else_=fallback)

def mockery_label():
    chosen=label('mockery')
    return case((chosen.is_(True),1),(chosen.is_(False),0),else_=None).label('mockery')

def analyze_content(session,pid,start,end):
    config=session.get(PulseConfig,pid);minimum=config.min_classified if config else 20
    # A per-actor disagreement cannot be silently turned into one piece label.
    consensus=lambda field:case((and_(func.count(field)==func.count(PulseMention.actor_id),func.min(field)==func.max(field)),func.min(field)),else_=None)
    mentions=select(PulseMention.document_id.label('doc'),consensus(PulseMention.sentiment).label('tone'),consensus(PulseMention.emotion).label('emotion')).join(
        PulseActor,and_(PulseActor.id==PulseMention.actor_id,PulseActor.project_id==pid,PulseActor.is_demo.is_(False),PulseActor.active.is_(True))).where(
        PulseMention.project_id==pid,PulseMention.is_demo.is_(False)).group_by(PulseMention.document_id).subquery()
    nstamp=func.coalesce(NewsArticle.published_at,NewsArticle.ingested_at)
    ai_used=case((and_(ContentAssessment.id.is_(None),ContentAnalysis.id.is_not(None)),1),else_=0).label('ai')
    news=select(NewsArticle.url.label('url'),label('sentiment').label('tone'),label('emotion').label('emotion'),
        mockery_label(),ai_used,ContentAnalysis.provider.label('provider'),ContentAnalysis.model.label('model')).outerjoin(ContentAnalysis,ai_fresh(NewsArticle,'news_id',pid)).outerjoin(
        ContentAssessment,and_(ContentAssessment.project_id==pid,ContentAssessment.news_id==NewsArticle.id,fresh(NewsArticle))).where(
        NewsArticle.project_id==pid,nstamp>=start,nstamp<end)
    pulse=select(PulseDocument.url.label('url'),label('sentiment',mentions.c.tone).label('tone'),
        label('emotion',mentions.c.emotion).label('emotion'),mockery_label(),ai_used,ContentAnalysis.provider.label('provider'),ContentAnalysis.model.label('model')).join(mentions,mentions.c.doc==PulseDocument.id).outerjoin(
        ContentAnalysis,ai_fresh(PulseDocument,'pulse_document_id',pid)).outerjoin(
        ContentAssessment,and_(ContentAssessment.project_id==pid,ContentAssessment.pulse_document_id==PulseDocument.id,fresh(PulseDocument))).where(
        PulseDocument.project_id==pid,PulseDocument.is_demo.is_(False),PulseDocument.published_at>=start,PulseDocument.published_at<end)
    corpus=union_all(news,pulse).subquery()
    provenance=session.execute(select(corpus.c.provider,corpus.c.model,func.count()).where(corpus.c.ai==1).group_by(
        corpus.c.provider,corpus.c.model).order_by(corpus.c.provider,corpus.c.model).limit(21)).all()
    same=lambda field:case((func.min(field)==func.max(field),func.min(field)),else_=None)
    pieces=select(corpus.c.url,same(corpus.c.tone).label('tone'),same(corpus.c.emotion).label('emotion'),same(corpus.c.mockery).label('mockery'),func.max(corpus.c.ai).label('ai')).group_by(corpus.c.url).subquery()
    grouped=session.execute(select(pieces.c.tone,pieces.c.emotion,pieces.c.mockery,pieces.c.ai,func.count()).group_by(pieces.c.tone,pieces.c.emotion,pieces.c.mockery,pieces.c.ai)).all()
    tone={'positive':0,'neutral':0,'negative':0};emotions={key:0 for key in ['joy','anger','surprise','fear','sadness']};total=mocked=mockery_n=ai_n=0
    for t,e,m,ai,n in grouped:
        total+=n
        ai_n+=n*ai
        if t in tone:tone[t]+=n
        if e in emotions:emotions[e]+=n
        if m is not None:mockery_n+=n;mocked+=n*m
    tone_n=sum(tone.values());emotion_n=sum(emotions.values())
    pct=lambda n,den:round(100*n/den,2) if den>=minimum else None
    score=round(100*(tone['positive']+.5*tone['neutral'])/tone_n,2) if tone_n>=minimum else None
    return dict(unit='URL guardada única del corpus del proyecto; coincidencias de URL exactas se agrupan.',pieces=total,ai_analyzed_pieces=ai_n,
        ai_provenance=[dict(provider=p,model=m,contract=CONTRACT,source_records=n) for p,m,n in provenance[:20]],ai_provenance_bounded=len(provenance)>20,
        tone_classified=tone_n,tone_coverage=round(100*tone_n/total,2) if total else None,
        tone=[dict(label=k,count=n,percentage=pct(n,tone_n)) for k,n in tone.items()],
        mood_index=score,mood='Sin cobertura suficiente' if score is None else 'Predominio favorable' if tone['positive']>tone['negative'] else 'Predominio desfavorable' if tone['negative']>tone['positive'] else 'Balance mixto',
        emotion_classified=emotion_n,emotions=[dict(emotion=k,count=n,percentage=pct(n,emotion_n)) for k,n in emotions.items()],
        mockery_classified=mockery_n,mockery_count=mocked,mockery_percentage=pct(mocked,mockery_n),minimum_classified=minimum,
        methodology='Porcentajes entre piezas clasificadas en cada dimensión; burla puede coexistir con tono o emoción. URL diferentes pueden corresponder al mismo contenido. Etiquetas contradictorias en una URL quedan sin clasificación en esa dimensión.')
