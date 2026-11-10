"""One shared, durable refresh per project; no per-reader scraping."""
from datetime import datetime
from sqlalchemy import String,Text,DateTime,ForeignKey,UniqueConstraint,CheckConstraint,Index,func
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow

class ProjectRefreshRun(Base):
 __tablename__='project_refresh_runs'
 id:Mapped[int]=mapped_column(primary_key=True)
 project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False,index=True)
 slot_key:Mapped[str]=mapped_column(String(80),nullable=False)
 trigger:Mapped[str]=mapped_column(String(12),nullable=False)
 requested_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
 status:Mapped[str]=mapped_column(String(20),nullable=False,default='queued')
 active_key:Mapped[str|None]=mapped_column(String(8),nullable=True,default='active')
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow,server_default=func.now())
 started_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 result_json:Mapped[str]=mapped_column(Text,nullable=False,default='{}')
 __table_args__=(UniqueConstraint('project_id','slot_key',name='uq_refresh_slot'),
  UniqueConstraint('project_id','active_key',name='uq_refresh_active_project'),
  CheckConstraint("trigger IN ('daily','manual')",name='ck_refresh_trigger'),
  CheckConstraint("status IN ('queued','running','succeeded','partial','failed','interrupted')",name='ck_refresh_status'),
  CheckConstraint("(status IN ('queued','running') AND active_key='active') OR (status NOT IN ('queued','running') AND active_key IS NULL)",name='ck_refresh_active_state'),
  Index('ix_refresh_project_finished','project_id','finished_at'))
