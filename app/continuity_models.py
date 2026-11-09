"""Immutable, account-level aggregate audience observations. No participant IDs."""
from datetime import datetime
from sqlalchemy import ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,String,Text,DateTime,BigInteger,Index
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base

class AudienceSnapshot(Base):
    __tablename__='audience_snapshots'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    actor_id:Mapped[int]=mapped_column(nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    network:Mapped[str]=mapped_column(String(20))
    url:Mapped[str]=mapped_column(Text)
    provider:Mapped[str]=mapped_column(String(30))
    measurement_id:Mapped[str]=mapped_column(String(80))
    contract_version:Mapped[str]=mapped_column(String(40),default='participating-accounts-v1')
    period_from:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    period_to:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    reference_from:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    reference_to:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    captured_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    participants:Mapped[int]=mapped_column(BigInteger)
    returning:Mapped[int]=mapped_column('returning_count',BigInteger)
    reference_participants:Mapped[int|None]=mapped_column(BigInteger,nullable=True)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    __table_args__=(
        ForeignKeyConstraint(['actor_id','project_id','is_demo'],['pulse_actors.id','pulse_actors.project_id','pulse_actors.is_demo'],name='fk_audience_actor'),
        UniqueConstraint('project_id','actor_id','network','url','provider','measurement_id','period_from','period_to','captured_at',name='uq_audience_capture'),
        CheckConstraint('NOT is_demo',name='ck_audience_real'),
        CheckConstraint("contract_version = 'participating-accounts-v1'",name='ck_audience_contract'),
        CheckConstraint("provider IN ('manual','apify_export')",name='ck_audience_provider'),
        CheckConstraint('participants >= 0 AND participants <= 9007199254740991 AND returning_count >= 0 AND returning_count <= participants',name='ck_audience_counts'),
        CheckConstraint('reference_participants IS NULL OR (reference_participants >= returning_count AND reference_participants <= 9007199254740991)',name='ck_audience_reference_count'),
        CheckConstraint('reference_from < reference_to AND reference_to = period_from AND period_from < period_to AND period_to <= captured_at',name='ck_audience_dates'),
        Index('ix_audience_window','project_id','actor_id','period_to'))
