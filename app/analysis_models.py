"""Versioned, project-scoped automatic content analysis work; no personal profiles."""
from datetime import datetime
from sqlalchemy import ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,String,Text,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow

class ContentAnalysis(Base):
    __tablename__='content_analyses'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    news_id:Mapped[int|None]=mapped_column(nullable=True)
    pulse_document_id:Mapped[int|None]=mapped_column(nullable=True)
    is_demo:Mapped[bool]=mapped_column(default=False)
    source_title:Mapped[str]=mapped_column(Text)
    source_body:Mapped[str]=mapped_column(Text)
    source_url:Mapped[str]=mapped_column(Text)
    source_sha256:Mapped[str]=mapped_column(String(64))
    contract_version:Mapped[str]=mapped_column(String(40),default='content-v1')
    state:Mapped[str]=mapped_column(String(20),default='queued',index=True)
    attempts:Mapped[int]=mapped_column(default=0)
    sentiment:Mapped[str|None]=mapped_column(String(12),nullable=True)
    emotion:Mapped[str|None]=mapped_column(String(12),nullable=True)
    mockery:Mapped[bool|None]=mapped_column(nullable=True)
    confidence:Mapped[float|None]=mapped_column(nullable=True)
    evidence:Mapped[str|None]=mapped_column(Text,nullable=True)
    provider:Mapped[str|None]=mapped_column(String(80),nullable=True)
    model:Mapped[str|None]=mapped_column(String(120),nullable=True)
    error_code:Mapped[str|None]=mapped_column(String(24),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    __table_args__=(
        ForeignKeyConstraint(['news_id','project_id'],['news_articles.id','news_articles.project_id'],name='fk_analysis_news'),
        ForeignKeyConstraint(['pulse_document_id','project_id','is_demo'],['pulse_documents.id','pulse_documents.project_id','pulse_documents.is_demo'],name='fk_analysis_pulse'),
        UniqueConstraint('project_id','news_id','source_sha256','contract_version',name='uq_analysis_news'),
        UniqueConstraint('project_id','pulse_document_id','source_sha256','contract_version',name='uq_analysis_pulse'),
        CheckConstraint('(news_id IS NULL) <> (pulse_document_id IS NULL)',name='ck_analysis_target'),
        CheckConstraint('NOT is_demo',name='ck_analysis_real'),
        CheckConstraint("state IN ('queued','processing','completed','needs_review','failed','stale')",name='ck_analysis_state'),
        CheckConstraint('attempts >= 0 AND attempts <= 1',name='ck_analysis_attempts'),
        CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',name='ck_analysis_confidence'),
        CheckConstraint("sentiment IS NULL OR sentiment IN ('positive','neutral','negative')",name='ck_analysis_tone'),
        CheckConstraint("emotion IS NULL OR emotion IN ('joy','anger','surprise','fear','sadness')",name='ck_analysis_emotion'))
