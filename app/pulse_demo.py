"""Clearly labeled synthetic fixtures; separated by composite demo FKs."""
from datetime import datetime,timedelta,timezone
import json
from sqlalchemy import select
from .pulse_models import PulseActor,PulseBatch,PulseDocument,PulseMention,PulseAccount,PulseRule
from .models import AuditEvent


def ensure_demo(session,pid,user_id):
    old=session.scalar(select(PulseActor.id).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(True)))
    if old:return dict(prepared=True,already_present=True,is_demo=True)
    now=datetime.now(timezone.utc)
    batch=PulseBatch(project_id=pid,provider='synthetic_fixture',dataset_ref='demo-v1',sha256='fixture-not-source-evidence',is_demo=True,created_by=user_id)
    session.add(batch);session.flush()
    for index,(positive,negative,neutral) in enumerate([(12,18,10),(18,4,3),(5,6,4)]):
        actor=PulseActor(project_id=pid,name='Actor de ejemplo '+chr(65+index),kind='primary' if index==0 else 'comparator',is_demo=True,created_by=user_id)
        session.add(actor);session.flush()
        for age,labels in [(0,['positive']*positive+['negative']*negative+['neutral']*neutral),
                           (10,['positive']*18+['negative']*6+['neutral']*6)]:
            for n,label in enumerate(labels):
                doc=PulseDocument(project_id=pid,batch_id=batch.id,network='press' if n%3==0 else 'facebook',
                    external_id=f'demo-{index}-{age}-{n}',url=f'https://example.org/demo/{index}/{age}/{n}',
                    title='Publicación ficticia sobre servicios públicos '+str(n+1),text='Registro inventado para probar el panel; no corresponde a personas ni mediciones reales.',
                    published_at=now-timedelta(days=age,minutes=10+n*9),collected_at=now,
                    views=1000+n*37 if n%2==0 else None,interactions=12+n,is_demo=True)
                session.add(doc);session.flush()
                session.add(PulseMention(project_id=pid,document_id=doc.id,actor_id=actor.id,is_demo=True,
                    sentiment=label,emotion='joy' if label=='positive' else 'anger' if label=='negative' else 'surprise',
                    method='synthetic_fixture:v1',version=1,reviewed_by=user_id))
        if index==0:
            for age,followers in [(2,1140),(0,1200)]:
                session.add(PulseAccount(project_id=pid,actor_id=actor.id,network='facebook',url='https://example.org/demo-account',
                    captured_at=now-timedelta(days=age),metrics=json.dumps(dict(followers=followers,posts=60,views=10000,interactions=640,
                        reach=None,impressions=None)),is_demo=True,created_by=user_id))
            for name,metric,threshold in [('Volumen del ejemplo','mentions',35),('Tono desfavorable del ejemplo','negative_share',40)]:
                session.add(PulseRule(project_id=pid,actor_id=actor.id,name=name,metric=metric,threshold=threshold,min_mentions=20,
                    is_demo=True,created_by=user_id))
    session.add(AuditEvent(project_id=pid,user_id=user_id,action='pulse.demo',target='fixture:v1'))
    session.commit();return dict(prepared=True,already_present=False,is_demo=True)
