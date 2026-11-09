"""Immutable findings and append-only operational review history."""
from datetime import datetime
from sqlalchemy import ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,String,Text,DateTime,Index,func
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow

class AlertIncident(Base):
    __tablename__='alert_incidents'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'))
    rule_id:Mapped[int]=mapped_column(nullable=False)
    actor_id:Mapped[int]=mapped_column(nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False)
    network:Mapped[str]=mapped_column(String(20))
    period_from:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    period_to:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    snapshot_json:Mapped[str]=mapped_column(Text)
    snapshot_sha256:Mapped[str]=mapped_column(String(64))
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())
    __table_args__=(ForeignKeyConstraint(['rule_id','project_id','actor_id','is_demo'],['pulse_rules.id','pulse_rules.project_id','pulse_rules.actor_id','pulse_rules.is_demo'],name='fk_alert_rule_scope'),
        UniqueConstraint('id','project_id',name='uq_alert_scope'),
        UniqueConstraint('project_id','rule_id','network','period_from','period_to',name='uq_alert_cut'),
        CheckConstraint('NOT is_demo',name='ck_alert_real'),CheckConstraint('period_from < period_to',name='ck_alert_period'),
        Index('ix_alert_period','project_id','period_to'))

TRANSITION_SQL="(previous_status = 'open' AND status IN ('acknowledged','resolved','dismissed')) OR (previous_status = 'acknowledged' AND status IN ('resolved','dismissed')) OR (previous_status IN ('resolved','dismissed') AND status = 'open')"
class AlertEvent(Base):
    __tablename__='alert_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'))
    alert_id:Mapped[int]=mapped_column(nullable=False)
    version:Mapped[int]=mapped_column(nullable=False)
    previous_status:Mapped[str]=mapped_column(String(20))
    status:Mapped[str]=mapped_column(String(20))
    note:Mapped[str]=mapped_column(Text,default='')
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,server_default=func.now())
    __table_args__=(ForeignKeyConstraint(['alert_id','project_id'],['alert_incidents.id','alert_incidents.project_id'],name='fk_alert_event_scope'),
        UniqueConstraint('alert_id','project_id','version',name='uq_alert_event_version'),
        CheckConstraint('version >= 1 AND version <= 1000',name='ck_alert_version'),
        CheckConstraint(TRANSITION_SQL,name='ck_alert_transition'),Index('ix_alert_event_project','project_id','alert_id'))
