"""Persisted content labels and manual review, with project/role boundaries."""
import json
import unicodedata
from datetime import datetime,timezone
from typing import Literal

from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,update,delete,func,and_,exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Topic,ArticleReview,ReviewTopic,ReviewChange,NewsArticle,AuditEvent
from .news_review import query_articles,article_record,iso_utc

TOPIC_ROLES={'admin','editor'}
REVIEW_ROLES={'admin','editor','analyst'}
STATUSES={'unreviewed','reviewed','needs_check'}


class StrictBody(BaseModel):
    model_config=ConfigDict(extra='forbid')


class TopicInput(StrictBody):
    name:str=Field(min_length=2,max_length=80)


class TopicUpdate(TopicInput):
    active:bool
    expected_version:int=Field(ge=1)


class ReviewInput(StrictBody):
    expected_version:int=Field(ge=0)
    topic_ids:list[int]=Field(default_factory=list,max_length=10)
    status:Literal['unreviewed','reviewed','needs_check']='reviewed'
    note:str=Field(default='',max_length=1000)


def topic_name(value):
    value=' '.join(unicodedata.normalize('NFKC',value).split())
    if not 2<=len(value)<=80 or any(unicodedata.category(c).startswith('C') for c in value):
        raise HTTPException(422,'El tema requiere de 2 a 80 caracteres de texto.')
    key=value.casefold()
    if len(key)>100:raise HTTPException(422,'El nombre normalizado del tema es demasiado largo.')
    return value,key


def topic_record(topic):
    return dict(id=topic.id,name=topic.name,active=topic.active,version=topic.version)


def save_review(session,pid,article_id,actor_id,body):
    if '\x00' in body.note:raise HTTPException(422,'La nota contiene un carácter nulo no admitido.')
    if len(set(body.topic_ids))!=len(body.topic_ids) or any(t<=0 for t in body.topic_ids):
        raise HTTPException(422,'Selecciona hasta diez temas distintos.')
    article=session.scalar(select(NewsArticle.id).where(NewsArticle.id==article_id,NewsArticle.project_id==pid))
    if article is None:raise HTTPException(404,'Publicación no disponible.')
    topics=session.scalars(select(Topic).where(Topic.project_id==pid,Topic.id.in_(body.topic_ids))).all()
    previous_topics=set(session.scalars(select(ReviewTopic.topic_id).join(ArticleReview,
                  and_(ArticleReview.id==ReviewTopic.review_id,ArticleReview.project_id==ReviewTopic.project_id))
                  .where(ReviewTopic.project_id==pid,ArticleReview.article_id==article_id)).all())
    if len(topics)!=len(body.topic_ids) or any(not t.active and t.id not in previous_topics for t in topics):
        raise HTTPException(422,'Un tema está archivado o no pertenece al proyecto. Solo se conservan etiquetas archivadas ya asignadas.')
    now=datetime.now(timezone.utc)
    try:
        review=session.scalar(select(ArticleReview).where(ArticleReview.project_id==pid,ArticleReview.article_id==article_id))
        if review is None:
            if body.expected_version!=0:raise HTTPException(409,'La revisión cambió. Vuelve a cargarla antes de guardar.')
            review=ArticleReview(project_id=pid,article_id=article_id,status=body.status,note=body.note.strip(),
                                 version=1,reviewed_by=actor_id,updated_at=now)
            session.add(review);session.flush();version=1
        else:
            version=body.expected_version+1
            claimed=session.execute(update(ArticleReview).where(ArticleReview.id==review.id,
                      ArticleReview.project_id==pid,ArticleReview.version==body.expected_version)
                      .values(version=version,status=body.status,note=body.note.strip(),reviewed_by=actor_id,updated_at=now),
                      execution_options={'synchronize_session':False})
            if claimed.rowcount!=1:
                session.rollback();raise HTTPException(409,'Otra persona guardó cambios. Recarga la revisión.')
        session.execute(delete(ReviewTopic).where(ReviewTopic.project_id==pid,ReviewTopic.review_id==review.id))
        for topic in topics:session.add(ReviewTopic(review_id=review.id,topic_id=topic.id,project_id=pid))
        snapshot=dict(status=body.status,note=body.note.strip(),topics=[dict(id=t.id,name=t.name) for t in sorted(topics,key=lambda x:x.id)])
        session.add(ReviewChange(project_id=pid,review_id=review.id,version=version,actor_id=actor_id,
                                 snapshot=json.dumps(snapshot,ensure_ascii=False),created_at=now))
        session.add(AuditEvent(project_id=pid,user_id=actor_id,action='review.save',target=f'{article_id}:v{version}'))
        session.commit()
        session.expire_all()
        return dict(article_id=article_id,version=version,updated_at=iso_utc(now),reviewed_by=actor_id,**snapshot)
    except IntegrityError:
        session.rollback();raise HTTPException(409,'La revisión cambió. Recarga antes de guardar.') from None


def install_review_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/topics')
    def topics(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        _,membership=allow(pid,user,session)
        rows=session.scalars(select(Topic).where(Topic.project_id==pid).order_by(Topic.name_key,Topic.id).limit(50)).all()
        return dict(topics=[topic_record(t) for t in rows],can_manage=membership.role in TOPIC_ROLES,
                    can_review=membership.role in REVIEW_ROLES)

    @app.post('/api/projects/{pid}/topics')
    def create_topic(pid:int,body:TopicInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=TOPIC_ROLES);name,key=topic_name(body.name)
        if session.scalar(select(func.count(Topic.id)).where(Topic.project_id==pid))>=50:
            raise HTTPException(409,'Máximo 50 temas, incluidos los archivados, en este piloto.')
        item=Topic(project_id=pid,name=name,name_key=key,created_by=user.id)
        try:
            session.add(item);session.flush()
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='topic.create',target=str(item.id)))
            session.commit();return topic_record(item)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'El tema ya existe; puedes reactivar el archivado.') from None

    @app.put('/api/projects/{pid}/topics/{topic_id}')
    def edit_topic(pid:int,topic_id:int,body:TopicUpdate,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=TOPIC_ROLES);name,key=topic_name(body.name)
        try:
            changed=session.execute(update(Topic).where(Topic.id==topic_id,Topic.project_id==pid,
                                    Topic.version==body.expected_version)
                                    .values(name=name,name_key=key,active=body.active,version=body.expected_version+1),
                                    execution_options={'synchronize_session':False})
            if changed.rowcount!=1:
                session.rollback();raise HTTPException(409,'Tema no disponible o modificado; vuelve a cargarlo.')
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='topic.update',target=f'{topic_id}:v{body.expected_version+1}'))
            session.commit();session.expire_all()
            return topic_record(session.scalar(select(Topic).where(Topic.id==topic_id,Topic.project_id==pid)))
        except IntegrityError:
            session.rollback();raise HTTPException(409,'Ya existe otro tema con ese nombre.') from None

    @app.get('/api/projects/{pid}/reviews')
    def review_list(pid:int,q:str='',days:int=0,status:str='all',topic_id:int=0,
                    user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        if status not in STATUSES|{'all'} or topic_id<0:raise HTTPException(422,'Filtro de revisión inválido.')
        if topic_id and session.scalar(select(Topic.id).where(Topic.id==topic_id,Topic.project_id==pid)) is None:
            raise HTTPException(404,'Tema no disponible.')
        try:statement=query_articles(pid,q=q,days=days)
        except ValueError as exc:raise HTTPException(422,str(exc))
        statement=statement.outerjoin(ArticleReview,and_(ArticleReview.article_id==NewsArticle.id,ArticleReview.project_id==pid))
        if status!='all':statement=statement.where(func.coalesce(ArticleReview.status,'unreviewed')==status)
        if topic_id:
            statement=statement.where(exists(select(ReviewTopic.review_id).where(ReviewTopic.project_id==pid,
                                      ReviewTopic.review_id==ArticleReview.id,ReviewTopic.topic_id==topic_id)))
        rows=session.scalars(statement.limit(101)).all();selected=rows[:100]
        reviews=session.scalars(select(ArticleReview).where(ArticleReview.project_id==pid,
                                ArticleReview.article_id.in_([a.id for a in selected]))).all()
        by_article={r.article_id:r for r in reviews}
        links=session.execute(select(ReviewTopic.review_id,Topic.id,Topic.name,Topic.active)
                              .join(Topic,and_(Topic.id==ReviewTopic.topic_id,Topic.project_id==ReviewTopic.project_id))
                              .where(ReviewTopic.project_id==pid,ReviewTopic.review_id.in_([r.id for r in reviews]))).all()
        labels={}
        for rid,tid,name,active in links:labels.setdefault(rid,[]).append(dict(id=tid,name=name,active=active))
        output=[]
        for article in selected:
            review=by_article.get(article.id)
            output.append(dict(article_record(article),review=dict(version=review.version if review else 0,
                   status=review.status if review else 'unreviewed',note=review.note if review else '',
                   reviewed_by=review.reviewed_by if review else None,updated_at=iso_utc(review.updated_at) if review else None,
                   topics=labels.get(review.id,[]) if review else [])))
        return dict(articles=output,limit=100,truncated=len(rows)>100)

    @app.put('/api/projects/{pid}/reviews/{article_id}')
    def write_review(pid:int,article_id:int,body:ReviewInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=REVIEW_ROLES)
        return save_review(session,pid,article_id,user.id,body)

    @app.get('/api/projects/{pid}/reviews/{article_id}/history')
    def history(pid:int,article_id:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        if session.scalar(select(NewsArticle.id).where(NewsArticle.id==article_id,NewsArticle.project_id==pid)) is None:
            raise HTTPException(404,'Publicación no disponible.')
        changes=session.scalars(select(ReviewChange).join(ArticleReview,and_(ArticleReview.id==ReviewChange.review_id,
                                       ArticleReview.project_id==ReviewChange.project_id))
                                .where(ReviewChange.project_id==pid,ArticleReview.article_id==article_id)
                                .order_by(ReviewChange.version.desc()).limit(101)).all()
        return dict(changes=[dict(version=c.version,actor_id=c.actor_id,created_at=iso_utc(c.created_at),
                                 **json.loads(c.snapshot)) for c in changes[:100]],truncated=len(changes)>100)
