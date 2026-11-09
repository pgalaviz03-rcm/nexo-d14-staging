"""Own-user delivery preferences; simulation-only outbox; no outbound calls."""
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from typing import Literal
import hashlib
from fastapi import Depends,HTTPException
from pydantic import Field,SecretStr,AwareDatetime
from sqlalchemy import select,update,func,and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .apify_port import Strict
from .models import ReportVersion,ReportRelease,AuditEvent
from .pulse_models import PlatformBrand
from .delivery_models import BriefingSchedule,DeliveryJob
from .delivery import next_occurrence,seal,unseal,mask,validate_destination,message_text,DisabledSender,DeliveryUnavailable
from .briefing import build_briefing
from .report_api import decode_snapshot
from .news_review import iso_utc

class ScheduleInput(Strict):
    channel:Literal['email','telegram']='email'
    frequency:Literal['daily','weekdays','weekly']='daily'
    local_time:str=Field(default='07:00',pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    timezone:str=Field(default='America/Mexico_City',min_length=1,max_length=80)
    weekday:int=Field(default=0,ge=0,le=6)
    lookback_days:Literal[1,7,30]=1
    enabled:bool=False
    destination:SecretStr|None=Field(default=None,max_length=254)
    authorized_destination:bool=False
    clear_destination:bool=False
    expected_version:int=Field(default=0,ge=0)

class MessagePreview(Strict):
    start:AwareDatetime|None=None
    end:AwareDatetime|None=None

def install_delivery_api(app,db,current_user,allow):
    def record(row):
        now=datetime.now(timezone.utc)
        fields=['channel','frequency','local_time','timezone','weekday','lookback_days','enabled','version']
        result={name:getattr(row,name) for name in fields} if row else dict(channel='email',frequency='daily',local_time='07:00',timezone='America/Mexico_City',weekday=0,lookback_days=1,enabled=False,version=0)
        result['next_scheduled_for']=iso_utc(next_occurrence(SimpleNamespace(**result),now)) if result['enabled'] else None
        result['destination_masked']=None;result['destination_problem']=False
        if row and row.destination_ciphertext:
            try:result['destination_masked']=mask(row.channel,unseal(row.destination_ciphertext))
            except HTTPException:result['destination_problem']=True
        result.update(actual_delivery_enabled=False,recipient_verification_pending=True,scheduler_running=False)
        return result

    @app.get('/api/projects/{pid}/briefing/delivery')
    def settings(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        row=session.get(BriefingSchedule,(pid,user.id))
        jobs=session.scalars(select(DeliveryJob).where(DeliveryJob.project_id==pid,DeliveryJob.user_id==user.id).order_by(DeliveryJob.id.desc()).limit(10)).all()
        return dict(settings=record(row),jobs=[dict(id=j.id,state=j.state,scheduled_for=iso_utc(j.scheduled_for),report_id=j.report_id,report_version=j.report_version,is_simulation=j.is_simulation) for j in jobs])

    @app.put('/api/projects/{pid}/briefing/delivery')
    def configure(pid:int,body:ScheduleInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        try:next_occurrence(body,datetime.now(timezone.utc))
        except (ValueError,OverflowError):raise HTTPException(422,'Revisa el horario o la zona horaria IANA.') from None
        previous=session.get(BriefingSchedule,(pid,user.id));value=body.destination.get_secret_value().strip() if body.destination else ''
        if body.clear_destination and value:raise HTTPException(422,'Elige reemplazar o borrar el destino, no ambas acciones.')
        encrypted=previous.destination_ciphertext if previous and previous.channel==body.channel and not body.clear_destination else ''
        if value:
            if not body.authorized_destination:raise HTTPException(422,'Confirma en el formulario que el destino está autorizado.')
            encrypted=seal(validate_destination(body.channel,value))
        values=body.model_dump(exclude={'destination','authorized_destination','clear_destination','expected_version'})
        values.update(destination_ciphertext=encrypted,version=body.expected_version+1,updated_at=datetime.now(timezone.utc))
        try:
            if not body.expected_version:session.add(BriefingSchedule(project_id=pid,user_id=user.id,**values))
            else:
                changed=session.execute(update(BriefingSchedule).where(BriefingSchedule.project_id==pid,BriefingSchedule.user_id==user.id,BriefingSchedule.version==body.expected_version).values(**values),execution_options={'synchronize_session':False})
                if changed.rowcount!=1:session.rollback();raise HTTPException(409,'La programación cambió. Vuelve a cargarla.')
            session.execute(update(DeliveryJob).where(DeliveryJob.project_id==pid,DeliveryJob.user_id==user.id,DeliveryJob.state!='cancelled').values(state='cancelled'))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='delivery.configure',target='v'+str(body.expected_version+1)+':'+body.channel))
            session.commit();session.expire_all();return record(session.get(BriefingSchedule,(pid,user.id)))
        except IntegrityError:session.rollback();raise HTTPException(409,'La programación ya existe o cambió.') from None

    @app.post('/api/projects/{pid}/briefing/delivery/preview')
    def preview(pid:int,body:MessagePreview,user=Depends(current_user),session:Session=Depends(db)):
        project,_=allow(pid,user,session)
        packet=build_briefing(session,pid,project.name,start=body.start,end=body.end)
        brand=session.get(PlatformBrand,1)
        return dict(text=message_text(packet,brand.name if brand else 'NEXO'),actual_delivery_enabled=False,
            source='current_cut',review_required=True,external_calls=0)

    @app.post('/api/projects/{pid}/briefing/delivery/simulate')
    def simulate(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        schedule=session.get(BriefingSchedule,(pid,user.id));now=datetime.now(timezone.utc)
        if not schedule or not schedule.enabled:raise HTTPException(409,'Guarda primero una programación preparada activa. Los envíos seguirán desconectados.')
        slot=next_occurrence(schedule,now)
        existing=session.scalar(select(DeliveryJob).where(DeliveryJob.project_id==pid,DeliveryJob.user_id==user.id,DeliveryJob.schedule_version==schedule.version,DeliveryJob.scheduled_for==slot))
        if existing:return dict(id=existing.id,state=existing.state,duplicate=True,is_simulation=True,external_calls=0)
        if session.scalar(select(func.count(DeliveryJob.id)).where(DeliveryJob.project_id==pid,DeliveryJob.user_id==user.id,DeliveryJob.created_at>=now-timedelta(days=1)))>=20:
            raise HTTPException(429,'Límite de 20 simulaciones por proyecto y cuenta en 24 horas.')
        rows=session.scalars(select(ReportVersion).join(ReportRelease,and_(ReportRelease.project_id==ReportVersion.project_id,ReportRelease.report_id==ReportVersion.report_id,ReportRelease.version==ReportVersion.version)).where(
            ReportVersion.project_id==pid).order_by(ReportRelease.id.desc()).limit(51)).all()
        chosen=None;packet=None
        for row in rows[:50]:
            snap=decode_snapshot(row)
            if snap.get('mode')!='local_documentary_briefing_v1':continue
            cut=snap['briefing'];a=datetime.fromisoformat(cut['filters']['start']);b=datetime.fromisoformat(cut['filters']['end'])
            if abs((b-a).total_seconds()-schedule.lookback_days*86400)<60 and b<=now and slot-b<=timedelta(days=schedule.lookback_days):
                chosen=row;packet=cut;break
        brand=session.get(PlatformBrand,1);text=message_text(packet,brand.name if brand else 'NEXO') if packet else ''
        state='waiting_review' if chosen is None else 'blocked_recipient' if not schedule.destination_ciphertext else 'blocked_provider'
        job=DeliveryJob(project_id=pid,user_id=user.id,schedule_version=schedule.version,scheduled_for=slot,
            report_id=chosen.report_id if chosen else None,report_version=chosen.version if chosen else None,channel=schedule.channel,
            state=state,message=text,message_sha256=hashlib.sha256(text.encode()).hexdigest(),is_simulation=True)
        try:
            session.add(job);session.flush();session.add(AuditEvent(project_id=pid,user_id=user.id,action='delivery.simulate',target=str(job.id)));session.commit()
            return dict(id=job.id,state=state,duplicate=False,is_simulation=True,external_calls=0,source_search_bounded=len(rows)>50)
        except IntegrityError:
            session.rollback();existing=session.scalar(select(DeliveryJob).where(DeliveryJob.project_id==pid,DeliveryJob.user_id==user.id,DeliveryJob.schedule_version==schedule.version,DeliveryJob.scheduled_for==slot))
            if existing:return dict(id=existing.id,state=existing.state,duplicate=True,is_simulation=True,external_calls=0)
            raise HTTPException(409,'La simulación cambió. Recarga su estado.') from None

    @app.post('/api/projects/{pid}/briefing/delivery/send')
    def send_disabled(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        try:DisabledSender().send(destination='',text='',idempotency_key='')
        except DeliveryUnavailable as exc:raise HTTPException(409,str(exc))
