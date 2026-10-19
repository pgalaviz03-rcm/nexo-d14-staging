from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, UniqueConstraint, Index, Text, LargeBinary, func
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
