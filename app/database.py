import os
from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from .models import Base
from .config import validate_config
from sqlalchemy.orm import Session
from sqlalchemy import text


@event.listens_for(Session, 'after_begin')
def apply_actor(session, transaction, connection):
    # Reapply after EVERY commit/rollback; transaction-local settings never leak
    # through the connection pool and RSS's durable attempt commits keep identity.
    if connection.dialect.name == 'postgresql':
        for key in ('nexo.actor_id', 'nexo.auth_subject'):
            connection.execute(text('SELECT set_config(:key, :value, true)'),
                               {'key': key, 'value': str(session.info.get(key, ''))})

def create_database(url=None):
    db_url=url or os.getenv('DATABASE_URL','sqlite:///./storage/nexo.db')
    validate_config(db_url)
    if db_url.startswith('sqlite:'):
        name=make_url(db_url).database
        if name and name != ':memory:': Path(name).parent.mkdir(parents=True,exist_ok=True)
    connect_args={'check_same_thread':False} if db_url.startswith('sqlite:') else {}
    extra = {} if db_url.startswith('sqlite:') else {'pool_size': 3, 'max_overflow': 2, 'pool_timeout': 5,
        'connect_args': {'connect_timeout': 5}}
    engine=create_engine(db_url,pool_pre_ping=True,**(extra or {'connect_args': connect_args}))
    if engine.dialect.name=='postgresql':
        @event.listens_for(engine,'connect')
        def postgres_limits(conn,record):
            previous=conn.autocommit
            conn.autocommit=True
            try:
                with conn.cursor() as cur:
                    cur.execute('SET statement_timeout=8000')
                    cur.execute('SET idle_in_transaction_session_timeout=30000')
            finally:conn.autocommit=previous
    if db_url.startswith('sqlite:'):
        @event.listens_for(engine,'connect')
        def sqlite_fk(conn,record):conn.execute('PRAGMA foreign_keys=ON')
    return engine,sessionmaker(bind=engine,expire_on_commit=False)
