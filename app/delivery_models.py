"""Per-project content assessments and private, offline delivery planning."""
from datetime import datetime
from sqlalchemy import ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,Index,String,Text,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow

class ContentAssessment(Base):
    __tablename__='content_assessments'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    news_id:Mapped[int|None]=mapped_column(nullable=True)
    pulse_document_id:Mapped[int|None]=mapped_column(nullable=True)
    is_demo:Mapped[bool]=mapped_column(default=False)
    source_title:Mapped[str]=mapped_column(Text)
    source_body:Mapped[str]=mapped_column(Text)
    source_url:Mapped[str]=mapped_column(Text)
    source_sha256:Mapped[str]=mapped_column(String(64))
    sentiment:Mapped[str|None]=mapped_column(String(12),nullable=True)
    emotion:Mapped[str|None]=mapped_column(String(12),nullable=True)
    mockery:Mapped[bool|None]=mapped_column(nullable=True)
    reviewed_by:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    version:Mapped[int]=mapped_column(default=1)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    __table_args__=(ForeignKeyConstraint(['news_id','project_id'],['news_articles.id','news_articles.project_id'],name='fk_assessment_news'),
        ForeignKeyConstraint(['pulse_document_id','project_id','is_demo'],['pulse_documents.id','pulse_documents.project_id','pulse_documents.is_demo'],name='fk_assessment_pulse'),
        UniqueConstraint('project_id','news_id',name='uq_assessment_news'),UniqueConstraint('project_id','pulse_document_id',name='uq_assessment_pulse'),
        CheckConstraint('(news_id IS NULL) <> (pulse_document_id IS NULL)',name='ck_assessment_target'),
        CheckConstraint('NOT is_demo',name='ck_assessment_real'),CheckConstraint('version >= 1',name='ck_assessment_version'),
        CheckConstraint("sentiment IS NULL OR sentiment IN ('positive','neutral','negative')",name='ck_assessment_sentiment'),
        CheckConstraint("emotion IS NULL OR emotion IN ('joy','anger','surprise','fear','sadness')",name='ck_assessment_emotion'))

class BriefingSchedule(Base):
    __tablename__='briefing_schedules'
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True,index=True)
    channel:Mapped[str]=mapped_column(String(12))
    frequency:Mapped[str]=mapped_column(String(12))
    local_time:Mapped[str]=mapped_column(String(5))
    timezone:Mapped[str]=mapped_column(String(80))
    weekday:Mapped[int]=mapped_column(default=0)
    lookback_days:Mapped[int]=mapped_column(default=1)
    enabled:Mapped[bool]=mapped_column(default=False)
    destination_ciphertext:Mapped[str]=mapped_column(Text,default='')
    version:Mapped[int]=mapped_column(default=1)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    __table_args__=(CheckConstraint("channel IN ('email','telegram')",name='ck_schedule_channel'),
        CheckConstraint("frequency IN ('daily','weekdays','weekly')",name='ck_schedule_frequency'),
        CheckConstraint('weekday >= 0 AND weekday <= 6',name='ck_schedule_weekday'),
        CheckConstraint('lookback_days IN (1,7,30)',name='ck_schedule_lookback'),CheckConstraint('version >= 1',name='ck_schedule_version'))

class DeliveryJob(Base):
    __tablename__='delivery_jobs'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    schedule_version:Mapped[int]=mapped_column()
    scheduled_for:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    report_id:Mapped[int|None]=mapped_column(nullable=True)
    report_version:Mapped[int|None]=mapped_column(nullable=True)
    channel:Mapped[str]=mapped_column(String(12))
    state:Mapped[str]=mapped_column(String(24))
    message:Mapped[str]=mapped_column(Text,default='')
    message_sha256:Mapped[str]=mapped_column(String(64),default='')
    is_simulation:Mapped[bool]=mapped_column(default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    __table_args__=(ForeignKeyConstraint(['project_id','user_id'],['briefing_schedules.project_id','briefing_schedules.user_id'],name='fk_job_schedule'),
        ForeignKeyConstraint(['report_id','project_id','report_version'],['report_versions.report_id','report_versions.project_id','report_versions.version'],name='fk_job_report'),
        UniqueConstraint('project_id','user_id','schedule_version','scheduled_for',name='uq_job_occurrence'),
        CheckConstraint("state IN ('waiting_review','blocked_provider','blocked_recipient','cancelled')",name='ck_job_state'),
        CheckConstraint('is_simulation',name='ck_job_simulation'),
        CheckConstraint("channel IN ('email','telegram')",name='ck_job_channel'),
        CheckConstraint('(report_id IS NULL) = (report_version IS NULL)',name='ck_job_report_pair'),
        Index('ix_job_private_window','project_id','user_id','created_at'))
