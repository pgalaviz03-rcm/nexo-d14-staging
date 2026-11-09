"""Public actor dossiers; each record belongs to the existing actor/project."""
from datetime import datetime
from sqlalchemy import ForeignKey,ForeignKeyConstraint,CheckConstraint,String,Text,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow

class ActorProfile(Base):
    __tablename__='actor_profiles'
    actor_id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),index=True)
    is_demo:Mapped[bool]=mapped_column(default=False)
    public_role:Mapped[str]=mapped_column(String(160),default='')
    organization:Mapped[str]=mapped_column(String(160),default='')
    territory:Mapped[str]=mapped_column(String(160),default='')
    description:Mapped[str]=mapped_column(Text,default='')
    aliases_json:Mapped[str]=mapped_column(Text,default='[]')
    channels_json:Mapped[str]=mapped_column(Text,default='[]')
    version:Mapped[int]=mapped_column(default=1)
    updated_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    __table_args__=(ForeignKeyConstraint(['actor_id','project_id','is_demo'],
        ['pulse_actors.id','pulse_actors.project_id','pulse_actors.is_demo'],name='fk_profile_actor'),
        CheckConstraint('NOT is_demo',name='ck_actor_profile_real'),
        CheckConstraint('version >= 1',name='ck_actor_profile_version'))
