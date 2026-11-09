"""Read-only continuity by one account and declared measurement, never summed audiences."""
from datetime import datetime,timezone
import json
from fastapi import HTTPException
from sqlalchemy import select
from .pulse_models import PulseActor
from .actor_models import ActorProfile
from .continuity_models import AudienceSnapshot
from .network_service import aware,NETWORKS
from .pulse_service import window
from .news_review import iso_utc

MAX_RECORDS=1000
MIN_AUDIENCE=20
MIN_CELL=5

def metrics(row):
    empty=dict(participants=None,returning=None,new=None,reference_participants=None,return_rate=None,retention_rate=None)
    if row is None:return dict(**empty,status='pending',captured_at=None,reference=None)
    n,r,b=row.participants,row.returning,row.reference_participants
    cells=[r,n-r]+([b-r] if b is not None else [])
    hidden=n<MIN_AUDIENCE or (b is not None and b<MIN_AUDIENCE) or any(0<v<MIN_CELL for v in cells)
    values=empty if hidden else dict(participants=n,returning=r,new=n-r,reference_participants=b,
        return_rate=round(100*r/n,2) if n else None,retention_rate=round(100*r/b,2) if b else None)
    return dict(**values,status='limited_sample' if hidden else 'available',captured_at=iso_utc(row.captured_at),
        reference=dict(start=iso_utc(row.reference_from),end=iso_utc(row.reference_to)))

def overview(session,pid,*,actor_id=0,network='all',account_url='',measurement='',start=None,end=None,now=None):
    now=now or datetime.now(timezone.utc);start,end=window(start,end,now=now)
    if end>now:raise HTTPException(422,'El periodo no puede terminar en el futuro.')
    if network not in NETWORKS:raise HTTPException(422,'Red no admitida.')
    actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.active.is_(True),PulseActor.is_demo.is_(False))
        .order_by(PulseActor.kind.desc(),PulseActor.id).limit(50)).all()
    actor=next((a for a in actors if a.id==actor_id),None) if actor_id else next((a for a in actors if a.kind=='primary'),actors[0] if actors else None)
    if actor_id and not actor:raise HTTPException(404,'Actor no disponible en este proyecto.')
    profile=session.scalar(select(ActorProfile).where(ActorProfile.project_id==pid,ActorProfile.actor_id==actor.id)) if actor else None
    refs=json.loads(profile.channels_json) if profile else []
    accounts=[dict(network=r['network'],url=r['url']) for r in refs if r.get('enabled',True) and (network=='all' or r['network']==network)][:20]
    account=next((a for a in accounts if a['url']==account_url),None) if account_url else (accounts[0] if accounts else None)
    if account_url and not account:raise HTTPException(404,'Cuenta no disponible en este proyecto.')
    rows=[]
    if account:
        rows=session.scalars(select(AudienceSnapshot).where(AudienceSnapshot.project_id==pid,AudienceSnapshot.actor_id==actor.id,
            AudienceSnapshot.is_demo.is_(False),AudienceSnapshot.network==account['network'],AudienceSnapshot.url==account['url'],
            AudienceSnapshot.captured_at<=now,AudienceSnapshot.period_to<=end).order_by(AudienceSnapshot.captured_at.desc(),AudienceSnapshot.id.desc()).limit(MAX_RECORDS+1)).all()
    bounded=len(rows)>MAX_RECORDS;rows=rows[:MAX_RECORDS]
    definitions=list(dict.fromkeys(r.provider+':'+r.measurement_id for r in rows))
    if measurement and measurement not in definitions:raise HTTPException(404,'Medición no disponible para esta cuenta.')
    selected=measurement or next((r.provider+':'+r.measurement_id for r in rows if aware(r.period_from)==start and aware(r.period_to)==end),definitions[0] if definitions else '')
    rows=[r for r in rows if r.provider+':'+r.measurement_id==selected]
    def source(a,b):return next((r for r in rows if aware(r.period_from)==a and aware(r.period_to)==b),None)
    current_row=source(start,end);previous_row=source(start-(end-start),start)
    current,previous=metrics(current_row),metrics(previous_row)
    consistent=not (current_row and previous_row and current_row.reference_participants is not None and current_row.reference_participants!=previous_row.participants)
    delta=round(current['return_rate']-previous['return_rate'],2) if consistent and current['return_rate'] is not None and previous['return_rate'] is not None else None
    unique={}
    for row in rows:
        a,b=aware(row.period_from),aware(row.period_to)
        if start-(end-start)*11<=a and b-a==end-start:unique.setdefault((a,b),row)
    series=[dict(start=iso_utc(a),end=iso_utc(b),**metrics(r)) for (a,b),r in sorted(unique.items())][-12:]
    return dict(project_id=pid,actors=[dict(id=a.id,name=a.name,kind=a.kind) for a in actors],selected_actor_id=actor.id if actor else None,
        accounts=accounts,selected_account=dict(**account,actor_id=actor.id,actor_name=actor.name) if account else None,
        measurements=definitions,selected_measurement=selected,window=dict(start=iso_utc(start),end=iso_utc(end)),
        current=current,previous=previous,return_rate_change_pp=delta,baseline_consistent=consistent,series=series,
        coverage_bounded=bounded,query_limit=MAX_RECORDS,minimum_audience=MIN_AUDIENCE,minimum_nonzero_cell=MIN_CELL,
        contract_version='participating-accounts-v1',external_calls=0)
