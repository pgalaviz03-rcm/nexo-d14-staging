from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, ForeignKey, ForeignKeyConstraint, CheckConstraint, DateTime, UniqueConstraint, Index, Text, LargeBinary, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow(): return datetime.now(timezone.utc)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_subject: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,server_default=func.now())

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='active', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,server_default=func.now())

class Membership(Base):
    __tablename__='memberships'
    __table_args__=(UniqueConstraint('project_id','user_id',name='uq_membership'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    role: Mapped[str]=mapped_column(String(24),nullable=False) # admin, analyst, editor, viewer

class Dataset(Base):
    __tablename__='datasets'
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    uploaded_by: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    filename: Mapped[str]=mapped_column(String(255),nullable=False)
    media_type: Mapped[str]=mapped_column(String(120),nullable=False)
    sha256: Mapped[str]=mapped_column(String(64),nullable=False)
    size_bytes: Mapped[int]=mapped_column(Integer,nullable=False)
    status: Mapped[str]=mapped_column(String(32),nullable=False,default='staged')
    record_count: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    detail: Mapped[str]=mapped_column(Text,nullable=False,default='')
    path: Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())

class SectionMetric(Base):
    __tablename__='section_metrics'
    __table_args__=(UniqueConstraint('project_id','section','election_year',name='uq_project_section_year'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    section: Mapped[int]=mapped_column(Integer,nullable=False)
    election_year: Mapped[int]=mapped_column(Integer,nullable=False)
    nominal_list: Mapped[int]=mapped_column(Integer,nullable=False)
    territorial_votes: Mapped[int]=mapped_column(Integer,nullable=False)
    polling_places: Mapped[int]=mapped_column(Integer,nullable=False)
    null_votes: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    source: Mapped[str]=mapped_column(String(240),nullable=False)

class AuditEvent(Base):
    __tablename__='audit_events'
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int|None]=mapped_column(ForeignKey('projects.id'),nullable=True,index=True)
    user_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    action: Mapped[str]=mapped_column(String(64),nullable=False)
    target: Mapped[str]=mapped_column(String(160),nullable=False,default='')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())

Index('ix_section_project_year',SectionMetric.project_id,SectionMetric.election_year)

class FeedSource(Base):
    __tablename__ = 'feed_sources'
    __table_args__ = (UniqueConstraint('project_id','url',name='uq_feed_project_url'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    url: Mapped[str] = mapped_column(String(1500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending')
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,server_default=func.now())

class NewsArticle(Base):
    __tablename__ = 'news_articles'
    __table_args__ = (UniqueConstraint('project_id','url_hash',name='uq_article_project_url_hash'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    feed_id: Mapped[int | None] = mapped_column(ForeignKey('feed_sources.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(650), nullable=False)
    url: Mapped[str] = mapped_column(String(1500), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    publisher: Mapped[str] = mapped_column(String(180), nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False, default='')
    origin: Mapped[str] = mapped_column(String(32), nullable=False) # rss | csv
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,server_default=func.now())

Index('ix_article_project_published',NewsArticle.project_id,NewsArticle.published_at)


class DatasetBlob(Base):
    __tablename__ = 'dataset_blobs'
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class UsageCounter(Base):
    __tablename__ = 'usage_counters'
    __table_args__ = (UniqueConstraint('project_id', 'action', 'bucket', name='uq_usage_bucket'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# Composite references keep reviews and labels inside the article's project.
article_scope_index=Index('uq_article_id_project_review',NewsArticle.id,NewsArticle.project_id,unique=True)


class Topic(Base):
    __tablename__='topics'
    __table_args__=(UniqueConstraint('project_id','name_key',name='uq_topic_project_name'),
                   UniqueConstraint('id','project_id',name='uq_topic_id_project'),
                   CheckConstraint('version >= 1',name='ck_topic_version'))
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    name: Mapped[str]=mapped_column(String(80),nullable=False)
    name_key: Mapped[str]=mapped_column(String(100),nullable=False)
    active: Mapped[bool]=mapped_column(default=True,nullable=False)
    version: Mapped[int]=mapped_column(default=1,nullable=False)
    created_by: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())


class ArticleReview(Base):
    __tablename__='article_reviews'
    __table_args__=(UniqueConstraint('project_id','article_id',name='uq_review_project_article'),
                   UniqueConstraint('id','project_id',name='uq_review_id_project'),
                   ForeignKeyConstraint(['article_id','project_id'],['news_articles.id','news_articles.project_id'],name='fk_review_article_scope'),
                   CheckConstraint("status IN ('unreviewed','reviewed','needs_check')",name='ck_review_status'),
                   CheckConstraint('version >= 1',name='ck_review_version'))
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    article_id: Mapped[int]=mapped_column(Integer,nullable=False,index=True)
    status: Mapped[str]=mapped_column(String(24),nullable=False)
    note: Mapped[str]=mapped_column(Text,nullable=False,default='')
    version: Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    reviewed_by: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())


class ReviewTopic(Base):
    __tablename__='review_topics'
    __table_args__=(ForeignKeyConstraint(['review_id','project_id'],['article_reviews.id','article_reviews.project_id'],name='fk_review_topic_review_scope'),
                   ForeignKeyConstraint(['topic_id','project_id'],['topics.id','topics.project_id'],name='fk_review_topic_label_scope'),
                   Index('ix_review_topic_label','project_id','topic_id'))
    review_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    topic_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)


class ReviewChange(Base):
    __tablename__='review_changes'
    __table_args__=(ForeignKeyConstraint(['review_id','project_id'],['article_reviews.id','article_reviews.project_id'],name='fk_change_review_scope'),
                   UniqueConstraint('review_id','version',name='uq_change_review_version'),
                   Index('ix_change_project_review','project_id','review_id'))
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    review_id: Mapped[int]=mapped_column(Integer,nullable=False)
    version: Mapped[int]=mapped_column(Integer,nullable=False)
    actor_id: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    snapshot: Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())


class Report(Base):
    __tablename__='reports'
    __table_args__=(UniqueConstraint('id','project_id',name='uq_report_id_project'),
                   CheckConstraint('current_version >= 1 AND current_version <= 50',name='ck_report_version'))
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    current_version: Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    created_by: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())


class ReportVersion(Base):
    __tablename__='report_versions'
    __table_args__=(ForeignKeyConstraint(['report_id','project_id'],['reports.id','reports.project_id'],name='fk_report_version_scope'),
                   UniqueConstraint('report_id','project_id','version',name='uq_report_project_version'),
                   CheckConstraint('version >= 1 AND version <= 50',name='ck_report_snapshot_version'),
                   Index('ix_report_version_project_report','project_id','report_id'))
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    report_id: Mapped[int]=mapped_column(Integer,nullable=False)
    version: Mapped[int]=mapped_column(Integer,nullable=False)
    payload: Mapped[str]=mapped_column(Text,nullable=False)
    sha256: Mapped[str]=mapped_column(String(64),nullable=False)
    created_by: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())


class ReportRelease(Base):
    __tablename__='report_releases'
    __table_args__=(ForeignKeyConstraint(['report_id','project_id','version'],
                    ['report_versions.report_id','report_versions.project_id','report_versions.version'],name='fk_report_release_version_scope'),
                   UniqueConstraint('report_id','project_id','version',name='uq_report_release_version'),
                   Index('ix_report_release_project_report','project_id','report_id'))
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
    report_id: Mapped[int]=mapped_column(Integer,nullable=False)
    version: Mapped[int]=mapped_column(Integer,nullable=False)
    published_by: Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())


# Register local observatory tables before Base.metadata.create_all in main.
from . import pulse_models as _pulse_models
from . import delivery_models as _delivery_models
from . import analysis_models as _analysis_models
from . import actor_models as _actor_models
from . import continuity_models as _continuity_models
from . import alert_models as _alert_models
