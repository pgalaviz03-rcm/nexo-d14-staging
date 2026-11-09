"""Read a live cut; freeze it in the established report/release boundary."""
from datetime import datetime
import hashlib,json
from fastapi import Depends,HTTPException
from pydantic import AwareDatetime,Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from .apify_port import Strict
from .briefing import build_briefing
from .models import Report,ReportVersion,AuditEvent
from .report_api import MAX_PAYLOAD_BYTES,WRITERS

class BriefingSave(Strict):
    start:AwareDatetime
    end:AwareDatetime
    preview_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    title:str=Field(min_length=3,max_length=140)
    note:str=Field(default='',max_length=2000)


def install_briefing_api(app,db,current_user,allow):
    def local_snapshot(session,write=False):
        if session.bind.dialect.name!='sqlite':return
        connection=session.connection()
        # Python sqlite legacy mode otherwise starts no transaction for SELECT.
        # One cut must read one state; saving takes the write lock before reads.
        if not connection.connection.driver_connection.in_transaction:
            try:connection.exec_driver_sql('BEGIN IMMEDIATE' if write else 'BEGIN')
            except OperationalError:raise HTTPException(409,'La copia local está ocupada. Vuelve a intentar el corte en unos segundos.') from None

    @app.get('/api/projects/{pid}/briefing')
    def preview(pid:int,start:datetime|None=None,end:datetime|None=None,user=Depends(current_user),session:Session=Depends(db)):
        local_snapshot(session)
        project,member=allow(pid,user,session)
        packet=build_briefing(session,pid,project.name,start=start,end=end)
        return dict(**packet,can_save=member.role in WRITERS)

    @app.post('/api/projects/{pid}/briefing/reports')
    def save(pid:int,body:BriefingSave,user=Depends(current_user),session:Session=Depends(db)):
        local_snapshot(session,write=True)
        project,_=allow(pid,user,session,roles=WRITERS)
        title=' '.join(body.title.split())
        if len(title)<3 or any(ord(c)<32 or ord(c)==127 for c in title) or '\x00' in body.note:
            raise HTTPException(422,'Revisa el título y la nota editorial.')
        packet=build_briefing(session,pid,project.name,start=body.start,end=body.end)
        if packet['preview_sha256']!=body.preview_sha256:
            raise HTTPException(409,'La evidencia del corte cambió. Actualiza Briefing y revísalo antes de guardar; tu nota se conserva.')
        if not packet['citations']:raise HTTPException(422,'No hay publicaciones con fuentes en este corte para guardar un briefing.')
        payload=dict(mode=packet['mode'],title=title,editorial_note=body.note.strip(),
            context=dict(project_id=pid,question='Briefing documental del proyecto',citations=packet['citations'],coverage=packet['coverage']),
            filters=dict(source_kind='all',days=0,limit=14),briefing=packet,prepared_at=packet['prepared_at'],
            scope=packet['interpretation'],ai_used=packet['ai_used'],external_calls=0)
        raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        try:encoded=raw.encode('utf-8')
        except UnicodeEncodeError:raise HTTPException(422,'Texto Unicode no admitido.') from None
        if len(encoded)>MAX_PAYLOAD_BYTES:raise HTTPException(422,'El briefing supera el tamaño permitido. Reduce la nota o revisa las fuentes.')
        digest=hashlib.sha256(encoded).hexdigest()
        report=Report(project_id=pid,created_by=user.id,current_version=1);session.add(report);session.flush()
        session.add(ReportVersion(project_id=pid,report_id=report.id,version=1,payload=raw,sha256=digest,created_by=user.id))
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='briefing.save',target=f'{report.id}:v1'))
        session.commit();return dict(id=report.id,version=1,sha256=digest,published=False)
