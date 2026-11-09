"""Aggregate public-content metrics; no inference about individual citizens."""
from collections import defaultdict
from datetime import datetime,timedelta,timezone
import json
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import select,func,and_
from .models import NewsArticle
from .pulse_models import PulseActor,PulseConfig,PulseDocument,PulseMention,PulseAccount,PulseRule
from .news_review import iso_utc

UTC=timezone.utc


def utc(value):
    if value.tzinfo is None:raise HTTPException(422,'Las fechas deben incluir zona horaria.')
    return value.astimezone(UTC)


def window(start=None,end=None,now=None):
    now=now or datetime.now(UTC)
    if (start is None)!=(end is None):raise HTTPException(422,'Indica inicio y fin del periodo.')
    end=utc(end) if end else now;start=utc(start) if start else end-timedelta(days=1)
    if not timedelta(minutes=1)<=end-start<=timedelta(days=90):raise HTTPException(422,'Selecciona entre un minuto y 90 días.')
    return start,end


def aggregate(session,pid,start,end,network,demo):
    q=select(PulseMention.actor_id,PulseMention.sentiment,PulseMention.emotion,func.count()).join(
        PulseDocument,and_(PulseDocument.id==PulseMention.document_id,PulseDocument.project_id==PulseMention.project_id,
                           PulseDocument.is_demo==PulseMention.is_demo)).join(PulseActor,and_(
        PulseActor.id==PulseMention.actor_id,PulseActor.project_id==PulseMention.project_id,
        PulseActor.is_demo==PulseMention.is_demo)).where(PulseMention.project_id==pid,PulseMention.is_demo==demo,
        PulseActor.active.is_(True),PulseDocument.published_at>=start,PulseDocument.published_at<end)
    if network!='all':q=q.where(PulseDocument.network==network)
    rows=session.execute(q.group_by(PulseMention.actor_id,PulseMention.sentiment,PulseMention.emotion)).all()
    result=defaultdict(lambda:dict(mentions=0,positive=0,neutral=0,negative=0,emotions=defaultdict(int)))
    for actor,label,emotion,n in rows:
        row=result[actor];row['mentions']+=n
        if label:row[label]+=n
        if emotion:row['emotions'][emotion]+=n
    return result


def metrics(row,min_samples):
    n=row['positive']+row['neutral']+row['negative']
    return dict(mentions=row['mentions'],classified=n,classification_coverage=round(100*n/row['mentions'],2) if row['mentions'] else None,
        score=round(100*(row['positive']+.5*row['neutral'])/n,2) if n>=min_samples else None,
        positive=row['positive'],neutral=row['neutral'],negative=row['negative'],
        negative_share=round(100*row['negative']/n,2) if n>=min_samples else None)


def rule_evaluation(rule,current,previous,minimum):
    c=metrics(current,minimum);p=previous['mentions']
    value=c['mentions'] if rule.metric=='mentions' else c['negative_share'] if rule.metric=='negative_share' else (100*(c['mentions']/p-1) if p else None)
    reason='insufficient_mentions' if c['mentions']<rule.min_mentions else 'classification_pending' if rule.metric=='negative_share' and value is None else 'baseline_pending' if value is None else None
    return dict(status='waiting' if reason else 'triggered' if value>=rule.threshold else 'clear',reason=reason,
        value=round(value,2) if value is not None else None,mentions=c['mentions'],classified=c['classified'],
        classification_coverage=c['classification_coverage'],previous_mentions=p,minimum_classified=minimum)

def overview(session,pid,*,actor_id=0,start=None,end=None,network='all',demo=False):
    if network not in {'all','press','facebook','instagram','x','tiktok','youtube','other'}:raise HTTPException(422,'Canal no admitido.')
    start,end=window(start,end)
    config=session.get(PulseConfig,pid);minimum=config.min_classified if config else 20
    actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.is_demo==demo,
        PulseActor.active.is_(True)).order_by(PulseActor.kind.desc(),PulseActor.id).limit(51)).all()
    if actor_id and actor_id not in {a.id for a in actors}:raise HTTPException(404,'Actor no disponible en este proyecto y modo.')
    current=aggregate(session,pid,start,end,network,demo)
    previous=aggregate(session,pid,start-(end-start),start,network,demo)
    baseline=aggregate(session,pid,start-timedelta(days=90),start,network,demo)
    empty=lambda:dict(mentions=0,positive=0,neutral=0,negative=0,emotions={})
    total=sum(x['mentions'] for x in current.values());cards=[]
    for actor in actors[:50]:
        m=metrics(current.get(actor.id,empty()),minimum);b=metrics(baseline.get(actor.id,empty()),minimum)
        cards.append(dict(id=actor.id,name=actor.name,kind=actor.kind,**m,
            share=round(100*m['mentions']/total,2) if total else None,
            baseline_score=b['score'],baseline_classified=b['classified'],
            score_delta=round(m['score']-b['score'],2) if m['score'] is not None and b['score'] is not None else None))
    selected_rows=[current.get(actor_id,empty())] if actor_id else list(current.values())
    combined=empty();emotions=defaultdict(int)
    for row in selected_rows:
        for key in ['mentions','positive','neutral','negative']:combined[key]+=row[key]
        for key,n in row['emotions'].items():emotions[key]+=n
    m=metrics(combined,minimum)
    base_rows=[baseline.get(actor_id,empty())] if actor_id else list(baseline.values())
    base=empty()
    for row in base_rows:
        for key in ['mentions','positive','neutral','negative']:base[key]+=row[key]
    b=metrics(base,minimum)
    m.update(share=round(100*m['mentions']/total,2) if total else None,
        baseline_score=b['score'],baseline_classified=b['classified'],
        score_delta=round(m['score']-b['score'],2) if m['score'] is not None and b['score'] is not None else None)
    en=sum(emotions.values())
    emotion_rows=[dict(emotion=k,count=n,percentage=round(100*n/en,2)) for k,n in sorted(emotions.items(),key=lambda x:-x[1])] if en>=minimum else []
    rules=session.scalars(select(PulseRule).where(PulseRule.project_id==pid,PulseRule.is_demo==demo,
        PulseRule.active.is_(True),PulseRule.actor_id.in_([a.id for a in actors]))).all()
    alerts=[];evaluated=0
    for rule in rules:
        if actor_id and rule.actor_id!=actor_id:continue
        finding=rule_evaluation(rule,current.get(rule.actor_id,empty()),previous.get(rule.actor_id,empty()),minimum)
        if finding['status']=='waiting':continue
        evaluated+=1
        if finding['status']=='triggered':alerts.append(dict(rule_id=rule.id,actor_id=rule.actor_id,name=rule.name,metric=rule.metric,value=finding['value'],threshold=rule.threshold))
    docs=select(PulseDocument).join(PulseMention,and_(PulseMention.document_id==PulseDocument.id,
        PulseMention.project_id==PulseDocument.project_id,PulseMention.is_demo==PulseDocument.is_demo)).join(PulseActor,and_(
        PulseActor.id==PulseMention.actor_id,PulseActor.project_id==pid,PulseActor.is_demo==demo,PulseActor.active.is_(True))).where(PulseDocument.project_id==pid,PulseDocument.is_demo==demo,
        PulseDocument.published_at>=start,PulseDocument.published_at<end)
    if network!='all':docs=docs.where(PulseDocument.network==network)
    if actor_id:docs=docs.where(PulseMention.actor_id==actor_id)
    headlines=session.scalars(docs.distinct().order_by(PulseDocument.published_at.desc(),PulseDocument.id.desc()).limit(6)).all()
    ranked=[dict(id=d.id,title=d.title,url=d.url,network=d.network,source=urlsplit(d.url).hostname or d.network,published_at=iso_utc(d.published_at),views=None,
        interactions=d.interactions,rank_basis='date_only') for d in headlines]
    fallback=[]
    if not ranked and not demo and network in {'all','press'} and not actor_id:
        news=session.scalars(select(NewsArticle).where(NewsArticle.project_id==pid,
            func.coalesce(NewsArticle.published_at,NewsArticle.ingested_at)>=start,
            func.coalesce(NewsArticle.published_at,NewsArticle.ingested_at)<end).order_by(
                func.coalesce(NewsArticle.published_at,NewsArticle.ingested_at).desc(),NewsArticle.id.desc()).limit(6)).all()
        fallback=[dict(id=n.id,title=n.title,url=n.url,network='press',source=n.publisher,published_at=iso_utc(n.published_at or n.ingested_at),views=None,interactions=None,rank_basis='archive_date_only') for n in news]
    account_actor=actor_id or next((a.id for a in actors if a.kind=='primary'),None)
    accounts=[];bounded=False
    if account_actor:
        query=select(PulseAccount).where(PulseAccount.project_id==pid,PulseAccount.actor_id==account_actor,
            PulseAccount.is_demo==demo,PulseAccount.captured_at<end)
        if network!='all':query=query.where(PulseAccount.network==network)
        rows=session.scalars(query.order_by(PulseAccount.captured_at.desc()).limit(1001)).all();bounded=len(rows)>1000
        groups=defaultdict(list)
        for row in rows[:1000]:groups[(row.network,row.url)].append(row)
        bounded=bounded or len(groups)>20
        for (channel,url),snapshots in list(groups.items())[:20]:
            latest=snapshots[0];old=next((r for r in snapshots if (r.captured_at.replace(tzinfo=UTC) if r.captured_at.tzinfo is None else r.captured_at)<start),None)
            values=json.loads(latest.metrics);old_values=json.loads(old.metrics) if old else {}
            followers=values.get('followers');prior=old_values.get('followers')
            latest_at=latest.captured_at.replace(tzinfo=UTC) if latest.captured_at.tzinfo is None else latest.captured_at
            public_metrics={key:values.get(key) for key in ('followers','posts','interactions','metrics_from','metrics_to')}
            accounts.append(dict(network=channel,url=url,captured_at=iso_utc(latest.captured_at),metrics=public_metrics,
                followers_delta=followers-prior if followers is not None and prior is not None and latest_at>=start else None,
                stale=latest_at<start,
                baseline_at=iso_utc(old.captured_at) if old else None,
                series=[dict(at=iso_utc(r.captured_at),followers=json.loads(r.metrics).get('followers')) for r in reversed(snapshots[:30])]))
    latest=session.scalar(select(func.max(PulseDocument.collected_at)).where(PulseDocument.project_id==pid,PulseDocument.is_demo==demo))
    return dict(project_id=pid,is_demo=demo,window=dict(start=iso_utc(start),end=iso_utc(end),end_exclusive=True),
        selected_actor_id=actor_id,network=network,minimum_classified=minimum,metrics=m,actors=cards,emotions=emotion_rows,
        emotions_classified=en,alerts=alerts,alerts_evaluated=evaluated,active_alerts=len(alerts) if evaluated else None,
        rules_configured=len([r for r in rules if not actor_id or r.actor_id==actor_id]),
        headlines=ranked or fallback,accounts=accounts,account_actor_id=account_actor,account_coverage_bounded=bounded,
        latest_collection=iso_utc(latest),universe_mentions=total,territory=config.territory if config else '',
        comparison_window=dict(start=iso_utc(start-timedelta(days=90)),end=iso_utc(start)),
        methods=dict(score='(favorables + 0.5 × neutrales) / menciones clasificadas × 100',
            share='Menciones del actor / menciones de actores monitoreados, mismo proyecto, periodo y canal.',
            baseline='Tono de los 90 días previos al inicio; diferencia en puntos del índice.',
            volume_baseline='Periodo inmediatamente anterior de igual duración.',
            interpretation='Tono del contenido observado; no encuesta ni estimación del ánimo de la población.',
            headlines='Titulares ordenados por fecha de publicación; no se estima su audiencia.'),
        external_calls=0,ai_used=False)
