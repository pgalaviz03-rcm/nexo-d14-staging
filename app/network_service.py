"""Own-account statistics, not actor mentions or estimated voter sentiment."""
from datetime import datetime,timezone
import json
from fastapi import HTTPException
from sqlalchemy import select
from .pulse_models import PulseActor,PulseAccount
from .actor_models import ActorProfile
from .pulse_service import window
from .news_review import iso_utc

COUNTERS=('followers','posts','views','impressions','reach','interactions')
ACTIVITY=COUNTERS[1:]
MAX_RECORDS=1000
MAX_ACCOUNTS=20
NETWORKS={'all','facebook','instagram','x','tiktok','youtube','press','other'}

def aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def stamp(value):
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        return aware(dt) if dt.tzinfo is not None else None
    except (ValueError,AttributeError,TypeError):return None
def counter(value):return value if type(value) is int and 0<=value<=9007199254740991 else None
def change(value,previous):return dict(absolute=value-previous if value is not None and previous is not None else None,
    percent=round(100*(value-previous)/previous,2) if value is not None and previous is not None and previous>0 else None)

def account_packet(actor,key,history,reference,start,end):
    channel,url=key;stocks=[r for r in history if counter(r['metrics'].get('followers')) is not None]
    endpoints=[r for r in stocks if r['at']<=end];latest=stocks[0] if stocks else None
    at_cut=endpoints[0] if endpoints else None
    baseline=next((r for r in stocks if r['at']<=start),None)
    followers=counter(latest['metrics'].get('followers')) if latest else None
    prior=counter(baseline['metrics'].get('followers')) if baseline else None
    observed_change=change(followers,prior) if latest and baseline and latest['at']>start else dict(absolute=None,percent=None)
    previous_start=start-(end-start)
    def activity(a,b):
        row=next((r for r in history if stamp(r['metrics'].get('metrics_from'))==a and stamp(r['metrics'].get('metrics_to'))==b
            and b<=r['at']),None)
        return {key:counter(row['metrics'].get(key)) if row else None for key in ACTIVITY},row
    current,source=activity(start,end);previous,old=activity(previous_start,start)
    deltas={key:change(current[key],previous[key]) for key in ACTIVITY}
    series=[dict(at=iso_utc(r['at']),followers=counter(r['metrics'].get('followers'))) for r in reversed([r for r in endpoints if r['at']>=start][:30])]
    return dict(actor_id=actor.id,actor_name=actor.name,network=channel,url=url,registered=reference is not None,
        reference_review=reference.get('review','unreviewed') if reference else 'unreviewed',
        followers=followers,followers_as_of=iso_utc(latest['at']) if latest else None,
        followers_change=observed_change,followers_baseline_at=iso_utc(baseline['at']) if baseline else None,
        current=current,previous=previous,changes=deltas,activity_captured_at=iso_utc(source['at']) if source else None,
        activity_provider=source['metrics'].get('provider','legacy_record') if source else None,
        previous_captured_at=iso_utc(old['at']) if old else None,
        interactions_per_100_followers=round(100*current['interactions']/counter(at_cut['metrics'].get('followers')),2)
            if current['interactions'] is not None and at_cut and at_cut['at']>start and counter(at_cut['metrics'].get('followers')) else None,
        ratio_followers_as_of=iso_utc(at_cut['at']) if at_cut and at_cut['at']>start else None,
        series=series,series_limit=30,snapshots_in_query=len(history),
        status='no_captures' if not history else 'stale' if (not latest or latest['at']<=start) and not source else 'available')

def overview(session,pid,*,actor_id=0,network='all',account_url='',start=None,end=None,now=None):
    now=now or datetime.now(timezone.utc);start,end=window(start,end,now=now)
    if end>now:raise HTTPException(422,'El periodo no puede terminar en el futuro.')
    if network not in NETWORKS:raise HTTPException(422,'Red no admitida.')
    actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False),PulseActor.active.is_(True)).order_by(
        PulseActor.kind.desc(),PulseActor.id).limit(50)).all()
    selected=next((a for a in actors if a.id==actor_id),None) if actor_id else next((a for a in actors if a.kind=='primary'),actors[0] if actors else None)
    if actor_id and not selected:raise HTTPException(404,'Actor no disponible en este proyecto.')
    profiles={p.actor_id:p for p in session.scalars(select(ActorProfile).where(ActorProfile.project_id==pid)).all()}
    actor_accounts={};bounded=False
    for actor in actors:
        profile=profiles.get(actor.id);refs=json.loads(profile.channels_json) if profile else []
        enabled={(r['network'],r['url']):r for r in refs if r.get('enabled',True) and (network=='all' or r['network']==network)}
        paused={(r['network'],r['url']) for r in refs if not r.get('enabled',True)}
        query=select(PulseAccount).where(PulseAccount.project_id==pid,PulseAccount.actor_id==actor.id,
            PulseAccount.is_demo.is_(False),PulseAccount.captured_at<=now)
        if network!='all':query=query.where(PulseAccount.network==network)
        rows=session.scalars(query.order_by(PulseAccount.captured_at.desc(),PulseAccount.id.desc()).limit(MAX_RECORDS+1)).all()
        bounded=bounded or len(rows)>MAX_RECORDS;histories={}
        for row in rows[:MAX_RECORDS]:
            key=(row.network,row.url)
            if key in paused:continue
            histories.setdefault(key,[]).append(dict(at=aware(row.captured_at),metrics=json.loads(row.metrics)))
        keys=sorted(set(enabled)|set(histories),key=lambda k:(0 if k[0]=='facebook' else 1,k[0],k[1]))
        bounded=bounded or len(keys)>MAX_ACCOUNTS
        actor_accounts[actor.id]=[account_packet(actor,key,histories.get(key,[]),enabled.get(key),start,end) for key in keys[:MAX_ACCOUNTS]]
    accounts=actor_accounts.get(selected.id,[]) if selected else []
    focused=next((r for r in accounts if r['url']==account_url),None) if account_url else next(iter(accounts),None)
    if account_url and not focused:raise HTTPException(404,'Cuenta no disponible en el filtro actual.')
    comparison_network=focused['network'] if focused else network if network!='all' else 'facebook'
    comparison=[]
    for actor in actors:
        rows=[r for r in actor_accounts[actor.id] if r['network']==comparison_network]
        row=focused if selected and actor.id==selected.id else next(iter(rows),None)
        comparison.append(dict(actor_id=actor.id,actor_name=actor.name,kind=actor.kind,account=row))
    return dict(project_id=pid,selected_actor_id=selected.id if selected else None,
        actors=[dict(id=a.id,name=a.name,kind=a.kind) for a in actors],network=network,
        window=dict(start=iso_utc(start),end=iso_utc(end),end_exclusive=True),
        previous_window=dict(start=iso_utc(start-(end-start)),end=iso_utc(start),end_exclusive=True),
        accounts=accounts,selected_account=focused,comparison_network=comparison_network,comparison=comparison,
        coverage_bounded=bounded,query_limit_per_actor=MAX_RECORDS,accounts_limit_per_actor=MAX_ACCOUNTS,
        prepared_at=iso_utc(now),external_calls=0,
        methodology=dict(followers='Última observación disponible a la fecha de consulta; cambio entre observaciones con fechas explícitas, no crecimiento inferido de todo el periodo.',
            activity='Solo capturas con periodo declarado exactamente igual al corte; comparación con periodo anterior de igual duración.',
            comparison='Una cuenta por actor, misma red y periodo; no se suman audiencias ni alcances entre cuentas.',
            ratio='Interacciones del periodo / última observación de seguidores dentro del corte × 100. No es porcentaje de personas únicas.',
            identity='La cuenta es una referencia registrada o una captura existente; no es una verificación concedida por la red social.'))
