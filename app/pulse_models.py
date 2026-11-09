"""Generic project-scoped public-content observatory; no voter identity tables."""
from datetime import datetime
from sqlalchemy import String,Integer,BigInteger,ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,Index,Text,DateTime,func
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow


class PlatformGrant(Base):
    __tablename__='platform_grants'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    active:Mapped[bool]=mapped_column(default=True,nullable=False)
    scope_bindings:Mapped[str]=mapped_column(Text,default='{}',nullable=False)


class PlatformBrand(Base):
    __tablename__='platform_brand'
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(60),nullable=False)
    tagline:Mapped[str]=mapped_column(String(160),nullable=False,default='')
    __table_args__=(CheckConstraint('id = 1',name='ck_platform_brand_singleton'),)


class PulseConfig(Base):
    __tablename__='pulse_configs'
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),primary_key=True)
    territory:Mapped[str]=mapped_column(String(160),default='',nullable=False)
    min_classified:Mapped[int]=mapped_column(Integer,default=20,nullable=False)
    version:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    connector:Mapped[str]=mapped_column(Text,default='{}',nullable=False)
    __table_args__=(CheckConstraint('min_classified >= 3 AND min_classified <= 1000',name='ck_pulse_min'),CheckConstraint('version >= 1',name='ck_pulse_config_version'))


class PulseActor(Base):
    __tablename__='pulse_actors'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    name:Mapped[str]=mapped_column(String(120),nullable=False)
    kind:Mapped[str]=mapped_column(String(20),default='comparator',nullable=False)
    active:Mapped[bool]=mapped_column(default=True,nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    version:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    __table_args__=(UniqueConstraint('id','project_id','is_demo',name='uq_pulse_actor_scope'),
                   UniqueConstraint('project_id','name','is_demo',name='uq_pulse_actor_name'),
                   CheckConstraint("kind IN ('primary','comparator')",name='ck_pulse_actor_kind'))


class PulseBatch(Base):
    __tablename__='pulse_batches'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    provider:Mapped[str]=mapped_column(String(30),nullable=False)
    dataset_ref:Mapped[str]=mapped_column(String(100),nullable=False,default='')
    sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())
    __table_args__=(UniqueConstraint('id','project_id','is_demo',name='uq_pulse_batch_scope'),)


class PulseDocument(Base):
    __tablename__='pulse_documents'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    batch_id:Mapped[int]=mapped_column(Integer,nullable=False)
    network:Mapped[str]=mapped_column(String(20),nullable=False)
    external_id:Mapped[str]=mapped_column(String(200),nullable=False)
    url:Mapped[str]=mapped_column(Text,nullable=False)
    title:Mapped[str]=mapped_column(String(300),nullable=False)
    text:Mapped[str]=mapped_column(Text,nullable=False,default='')
    published_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    collected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    views:Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    interactions:Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    __table_args__=(ForeignKeyConstraint(['batch_id','project_id','is_demo'],['pulse_batches.id','pulse_batches.project_id','pulse_batches.is_demo'],name='fk_pulse_document_batch'),
        UniqueConstraint('id','project_id','is_demo',name='uq_pulse_document_scope'),
        UniqueConstraint('project_id','network','external_id','is_demo',name='uq_pulse_document_external'),
        Index('ix_pulse_document_window','project_id','is_demo','published_at'),
        CheckConstraint('views IS NULL OR views >= 0',name='ck_pulse_views'),CheckConstraint('interactions IS NULL OR interactions >= 0',name='ck_pulse_interactions'))


class PulseMention(Base):
    __tablename__='pulse_mentions'
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    document_id:Mapped[int]=mapped_column(Integer,primary_key=True)
    actor_id:Mapped[int]=mapped_column(Integer,primary_key=True)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    sentiment:Mapped[str|None]=mapped_column(String(12),nullable=True)
    emotion:Mapped[str|None]=mapped_column(String(12),nullable=True)
    method:Mapped[str]=mapped_column(String(60),default='unclassified',nullable=False)
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    version:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    __table_args__=(ForeignKeyConstraint(['document_id','project_id','is_demo'],['pulse_documents.id','pulse_documents.project_id','pulse_documents.is_demo'],name='fk_pulse_mention_document'),
        ForeignKeyConstraint(['actor_id','project_id','is_demo'],['pulse_actors.id','pulse_actors.project_id','pulse_actors.is_demo'],name='fk_pulse_mention_actor'),
        CheckConstraint("sentiment IS NULL OR sentiment IN ('positive','neutral','negative')",name='ck_pulse_sentiment'),
        CheckConstraint("emotion IS NULL OR emotion IN ('joy','anger','sadness','fear','surprise')",name='ck_pulse_emotion'),
        CheckConstraint('version >= 0',name='ck_pulse_mention_version'),Index('ix_pulse_mention_actor','project_id','actor_id'))


class PulseAccount(Base):
    __tablename__='pulse_accounts'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    actor_id:Mapped[int]=mapped_column(Integer,nullable=False)
    network:Mapped[str]=mapped_column(String(20),nullable=False)
    url:Mapped[str]=mapped_column(Text,nullable=False)
    captured_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    metrics:Mapped[str]=mapped_column(Text,nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    __table_args__=(ForeignKeyConstraint(['actor_id','project_id','is_demo'],['pulse_actors.id','pulse_actors.project_id','pulse_actors.is_demo'],name='fk_pulse_account_actor'),
        UniqueConstraint('project_id','actor_id','network','url','captured_at','is_demo',name='uq_pulse_account_snapshot'),
        Index('ix_pulse_account_time','project_id','actor_id','captured_at'))


class PulseRule(Base):
    __tablename__='pulse_rules'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    actor_id:Mapped[int]=mapped_column(Integer,nullable=False)
    name:Mapped[str]=mapped_column(String(100),nullable=False)
    metric:Mapped[str]=mapped_column(String(30),nullable=False)
    threshold:Mapped[int]=mapped_column(Integer,nullable=False)
    min_mentions:Mapped[int]=mapped_column(Integer,nullable=False,default=20)
    active:Mapped[bool]=mapped_column(default=True,nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    __table_args__=(ForeignKeyConstraint(['actor_id','project_id','is_demo'],['pulse_actors.id','pulse_actors.project_id','pulse_actors.is_demo'],name='fk_pulse_rule_actor'),
        CheckConstraint("metric IN ('mentions','negative_share','mention_spike')",name='ck_pulse_rule_metric'),
        CheckConstraint('threshold >= 1 AND threshold <= 1000000',name='ck_pulse_rule_threshold'),
        CheckConstraint('min_mentions >= 1',name='ck_pulse_rule_min'))


Index('uq_pulse_primary_actor',PulseActor.project_id,PulseActor.is_demo,unique=True,
      sqlite_where=(PulseActor.kind=='primary') & PulseActor.active,
      postgresql_where=(PulseActor.kind=='primary') & PulseActor.active)
Index('uq_pulse_rule_scope',PulseRule.id,PulseRule.project_id,PulseRule.actor_id,PulseRule.is_demo,unique=True)
