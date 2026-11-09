"""Read-only rule preview and immutable evidence packets from existing project data."""
from datetime import datetime,timezone
import json,hashlib
from fastapi import HTTPException
from sqlalchemy import select,and_,func,literal
from .models import Project
from .pulse_models import PulseActor,PulseRule,PulseConfig,PulseDocument,PulseMention
from .alert_models import AlertIncident,AlertEvent
from .pulse_service import window,aggregate,rule_evaluation
from .network_service import NETWORKS
from .news_review import iso_utc

STATES={'all','open','acknowledged','resolved','dismissed'}
TRANSITIONS={'open':{'acknowledged','resolved','dismissed'},'acknowledged':{'resolved','dismissed'},'resolved':{'open'},'dismissed':{'open'}}
MAX_INCIDENTS=200
def latest(session,pid,aid):
    return session.scalar(select(AlertEvent).where(AlertEvent.project_id==pid,AlertEvent.alert_id==aid).order_by(AlertEvent.version.desc()).limit(1))
def record(row,state='open',version=0):
    return dict(id=row.id,actor_id=row.actor_id,rule_id=row.rule_id,network=row.network,
        window=dict(start=iso_utc(row.period_from),end=iso_utc(row.period_to)),
        snapshot=json.loads(row.snapshot_json),snapshot_sha256=row.snapshot_sha256,created_at=iso_utc(row.created_at),status=state,version=version)
def detail(session,pid,aid):
    row=session.scalar(select(AlertIncident).where(AlertIncident.project_id==pid,AlertIncident.id==aid))
    if not row:raise HTTPException(404,'Incidente no disponible.')
    events=session.scalars(select(AlertEvent).where(AlertEvent.project_id==pid,AlertEvent.alert_id==aid).order_by(AlertEvent.version.desc()).limit(101)).all()
    current=events[0] if events else None
    return dict(**record(row,current.status if current else 'open',current.version if current else 0),
        history=[dict(version=e.version,previous_status=e.previous_status,status=e.status,note=e.note,by_user_id=e.created_by,at=iso_utc(e.created_at)) for e in reversed(events[:100])],history_bounded=len(events)>100)
def preview(session,pid,*,actor_id=0,network='all',start=None,end=None,now=None):
    now=now or datetime.now(timezone.utc);start,end=window(start,end,now=now)
    if end>now:raise HTTPException(422,'El corte no puede terminar en el futuro.')
    if network not in NETWORKS:raise HTTPException(422,'Canal no admitido.')
    actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False)).order_by(PulseActor.kind.desc(),PulseActor.id).limit(100)).all()
    if actor_id and actor_id not in {a.id for a in actors}:raise HTTPException(404,'Actor no disponible en este proyecto.')
    active={a.id:a for a in actors if a.active and (not actor_id or a.id==actor_id)}
    config=session.get(PulseConfig,pid);minimum=config.min_classified if config else 20
    current=aggregate(session,pid,start,end,network,False);previous=aggregate(session,pid,start-(end-start),start,network,False)
    empty=lambda:dict(mentions=0,positive=0,neutral=0,negative=0,emotions={})
    rules=session.scalars(select(PulseRule).where(PulseRule.project_id==pid,PulseRule.is_demo.is_(False),PulseRule.actor_id.in_(list(active))).order_by(PulseRule.id).limit(100)).all()
    readings=[]
    for r in rules:
        finding=rule_evaluation(r,current.get(r.actor_id,empty()),previous.get(r.actor_id,empty()),minimum)
        if not r.active:finding.update(status='paused',reason='paused',value=None)
        readings.append(dict(id=r.id,actor_id=r.actor_id,actor_name=active[r.actor_id].name,name=r.name,metric=r.metric,
            threshold=r.threshold,min_mentions=r.min_mentions,active=r.active,**finding))
    return dict(project_id=pid,actors=[dict(id=a.id,name=a.name,active=a.active) for a in actors],
        window=dict(start=iso_utc(start),end=iso_utc(end)),network=network,readings=readings,external_calls=0)
def overview(session,pid,*,state='all',**filters):
    if state not in STATES:raise HTTPException(422,'Estado no admitido.')
    packet=preview(session,pid,**filters);w=packet['window']
    current=select(AlertEvent.status).where(AlertEvent.alert_id==AlertIncident.id,AlertEvent.project_id==AlertIncident.project_id).order_by(AlertEvent.version.desc()).limit(1).correlate(AlertIncident).scalar_subquery()
    version=select(AlertEvent.version).where(AlertEvent.alert_id==AlertIncident.id,AlertEvent.project_id==AlertIncident.project_id).order_by(AlertEvent.version.desc()).limit(1).correlate(AlertIncident).scalar_subquery()
    q=select(AlertIncident,func.coalesce(current,literal('open')),func.coalesce(version,0)).where(AlertIncident.project_id==pid,
        AlertIncident.period_to>datetime.fromisoformat(w['start']),AlertIncident.period_to<=datetime.fromisoformat(w['end']))
    if filters.get('actor_id'):q=q.where(AlertIncident.actor_id==filters['actor_id'])
    if packet['network']!='all':q=q.where(AlertIncident.network==packet['network'])
    if state!='all':q=q.where(func.coalesce(current,literal('open'))==state)
    rows=session.execute(q.order_by(AlertIncident.created_at.desc(),AlertIncident.id.desc()).limit(MAX_INCIDENTS+1)).all()
    incidents=[record(r,s,v) for r,s,v in rows[:MAX_INCIDENTS]]
    return dict(**packet,incidents=incidents,incidents_bounded=len(rows)>MAX_INCIDENTS,incident_limit=MAX_INCIDENTS,
        counts={s:sum(r['status']==s for r in incidents) for s in STATES if s!='all'},count_scope='Listed incidents whose cut closes inside the selected period')
def evidence(session,pid,reading,start,end,network):
    q=select(PulseDocument).join(PulseMention,and_(PulseMention.document_id==PulseDocument.id,PulseMention.project_id==PulseDocument.project_id,PulseMention.is_demo==PulseDocument.is_demo)).where(
        PulseDocument.project_id==pid,PulseDocument.is_demo.is_(False),PulseMention.actor_id==reading['actor_id'],PulseDocument.published_at>=start,PulseDocument.published_at<end)
    if network!='all':q=q.where(PulseDocument.network==network)
    if reading['metric']=='negative_share':q=q.where(PulseMention.sentiment=='negative')
    docs=session.scalars(q.order_by(PulseDocument.published_at.desc(),PulseDocument.id.desc()).limit(21)).all()
    sources=[dict(document_id=d.id,title=d.title,url=d.url,network=d.network,published_at=iso_utc(d.published_at)) for d in docs[:20]]
    packet=dict(contract='alert-evidence-v1',reading=reading,sources=sources,sources_bounded=len(docs)>20,
        source_scope='Up to twenty observed pieces; not the full denominator',window=dict(start=iso_utc(start),end=iso_utc(end)),network=network)
    raw=json.dumps(packet,ensure_ascii=False,sort_keys=True);return raw,hashlib.sha256(raw.encode()).hexdigest()
