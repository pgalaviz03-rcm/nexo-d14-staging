"""Deterministic project brief from saved evidence. No generation or providers."""
from datetime import datetime,timezone
import hashlib,json
from sqlalchemy import select,func,and_
from .models import NewsArticle,ArticleReview,ReviewTopic,Topic,Dataset
from .pulse_models import PulseDocument
from .pulse_service import overview,window
from .news_review import iso_utc
from .briefing_analytics import analyze_content

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def build_briefing(session,pid,project_name,*,start=None,end=None):
    start,end=window(start,end)
    stamp=func.coalesce(NewsArticle.published_at,NewsArticle.ingested_at)
    scope=[NewsArticle.project_id==pid,stamp>=start,stamp<end]
    total=session.scalar(select(func.count(NewsArticle.id)).where(*scope))
    missing=session.scalar(select(func.count(NewsArticle.id)).where(*scope,NewsArticle.published_at.is_(None)))
    sources=session.execute(select(NewsArticle.publisher,func.count()).where(*scope).group_by(NewsArticle.publisher).order_by(func.count().desc(),NewsArticle.publisher).limit(21)).all()
    join=and_(ArticleReview.article_id==NewsArticle.id,ArticleReview.project_id==pid)
    reviews=session.execute(select(ArticleReview.status,func.count(NewsArticle.id)).select_from(NewsArticle).outerjoin(ArticleReview,join).where(*scope).group_by(ArticleReview.status)).all()
    statuses={'unreviewed':0,'reviewed':0,'needs_check':0}
    for status,n in reviews:statuses[status or 'unreviewed']+=n
    topic_rows=session.execute(select(Topic.name,Topic.active,func.count(func.distinct(NewsArticle.id))).select_from(NewsArticle).join(ArticleReview,join).join(
        ReviewTopic,and_(ReviewTopic.review_id==ArticleReview.id,ReviewTopic.project_id==pid)).join(Topic,and_(Topic.id==ReviewTopic.topic_id,Topic.project_id==pid)).where(*scope).group_by(Topic.id,Topic.name,Topic.active).order_by(func.count(func.distinct(NewsArticle.id)).desc(),Topic.id).limit(9)).all()
    rows=session.execute(select(NewsArticle,ArticleReview.status).outerjoin(ArticleReview,join).where(*scope).order_by(stamp.desc(),NewsArticle.id.desc()).limit(8)).all()
    citations=[];news=[]
    for article,status in rows:
        excerpt=(article.title+'\n'+article.abstract)[:1600]
        ref='N'+str(article.id)
        citations.append(dict(citation=ref,project_id=pid,kind='news',title=article.title,source=article.publisher,url=article.url,
            excerpt=excerpt,published_at=iso_utc(article.published_at),content_sha256=hashlib.sha256(excerpt.encode()).hexdigest()))
        news.append(dict(citation=ref,title=article.title,source=article.publisher,url=article.url,excerpt=article.abstract[:320],
            at=iso_utc(article.published_at or article.ingested_at),date_basis='publication' if article.published_at else 'ingestion',review_status=status or 'unreviewed'))
    pulse=overview(session,pid,start=start,end=end,network='all',demo=False)
    pulse_sources=[]
    for headline in pulse['headlines']:
        if headline['rank_basis']=='archive_date_only':continue
        row=session.scalar(select(PulseDocument).where(PulseDocument.project_id==pid,PulseDocument.is_demo.is_(False),PulseDocument.id==headline['id']))
        if row is None:continue
        excerpt=(row.title+'\n'+row.text)[:1600];ref='P'+str(row.id)
        citations.append(dict(citation=ref,project_id=pid,kind='public_content',title=row.title,source=row.network,url=row.url,
            excerpt=excerpt,published_at=iso_utc(row.published_at),content_sha256=hashlib.sha256(excerpt.encode()).hexdigest()))
        pulse_sources.append(dict(citation=ref,title=row.title,url=row.url,network=row.network,at=iso_utc(row.published_at)))
    compact=dict(metrics=pulse['metrics'],minimum_classified=pulse['minimum_classified'],
        alerts=pulse['alerts'][:5],active_alerts=pulse['active_alerts'],rules_configured=pulse['rules_configured'],alerts_evaluated=pulse['alerts_evaluated'],
        latest_collection=pulse['latest_collection'],sources=pulse_sources,
        methods=pulse['methods'],actor_count=len(pulse['actors']))
    packet=dict(mode='local_documentary_briefing_v1',project_id=pid,project_name=project_name,
        filters=dict(start=iso_utc(start),end=iso_utc(end),end_exclusive=True),
        news_count=total,news_without_publication_date=missing,review_status=statuses,news=news,
        sources=[dict(name=name,count=n) for name,n in sources[:20]],
        topics=[dict(name=name,active=active,count=n) for name,active,n in topic_rows[:8]],
        documents_in_archive=session.scalar(select(func.count(Dataset.id)).where(Dataset.project_id==pid)),
        pulse=compact,citations=citations,content_analytics=analyze_content(session,pid,start,end),
        coverage=dict(news_limit=8,news_truncated=total>8,source_list_bounded=len(sources)>20,topic_list_bounded=len(topic_rows)>8,
            pulse_source_limit=6,alert_list_limit=5,alert_list_bounded=len(pulse['alerts'])>5,not_indexed=[],
            bounded=total>8 or len(sources)>20 or len(topic_rows)>8 or len(pulse['alerts'])>5),
        interpretation='Lectura del archivo del proyecto. Tono del contenido clasificado, no encuesta. Revisado no significa verificado. No hay análisis generativo ni recomendaciones automáticas.',
        ai_used=False,external_calls=0,is_demo=False)
    packet['ai_used']=packet['content_analytics']['ai_analyzed_pieces']>0
    packet['preview_sha256']=digest(packet)
    packet['prepared_at']=iso_utc(datetime.now(timezone.utc))
    return packet
