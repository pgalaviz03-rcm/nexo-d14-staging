"""Local, cited documentary reports: append-only versions and explicit release.

No network or model is called. Retrieval runs again on each save; source packets
supplied by a browser are never trusted or accepted. All queries carry pid.
"""
import hashlib
import json
from datetime import datetime,timezone
from typing import Literal

from fastapi import Depends,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,update,exists,and_,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .evidence_search import retrieve_context
from .models import Report,ReportVersion,ReportRelease,AuditEvent,Project
from .report_document import origin,render_document
from .news_review import iso_utc

WRITERS={'admin','editor','analyst'}
PUBLISHERS={'admin','editor'}
MAX_PAYLOAD_BYTES=64*1024


class ReportInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=3,max_length=140)
    question:str=Field(min_length=2,max_length=240)
    note:str=Field(default='',max_length=2000)
    source_kind:Literal['all','news','documents']='all'
    days:Literal[0,1,7,30]=0
    limit:int=Field(default=5,ge=1,le=8)
    document_id:int|None=Field(default=None,ge=1)


class ReportRevision(ReportInput):
    expected_version:int=Field(ge=1,le=49)


class ReleaseInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=1,le=50)


def encode_snapshot(session,pid,body,uploads):
    title=' '.join(body.title.split())
    if len(title)<3 or any(ord(c)<32 or ord(c)==127 for c in title) or '\x00' in body.note:
        raise HTTPException(422,'Revisa el título o la nota del informe.')
    try:
        packet=retrieve_context(session,pid,body.question.strip(),uploads,limit=body.limit,
                                source_kind=body.source_kind,days=body.days,document_id=body.document_id)
    except ValueError as exc:raise HTTPException(422,str(exc))
    if not packet['citations']:
        raise HTTPException(422,'No hay coincidencias para guardar un informe con fuentes. Cambia la búsqueda o añade un documento.')
    payload=dict(title=title,editorial_note=body.note.strip(),context=packet,
                 filters=dict(source_kind=body.source_kind,days=body.days,limit=body.limit,document_id=body.document_id),
                 prepared_at=iso_utc(datetime.now(timezone.utc)),
                 scope='Extractos del archivo y nota del autor; no es una medición de opinión ni verificación automática de hechos.',
                 ai_used=False,external_calls=0)
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    try:encoded=raw.encode('utf-8')
    except UnicodeEncodeError:raise HTTPException(422,'El informe contiene texto Unicode no admitido.') from None
    if len(encoded)>MAX_PAYLOAD_BYTES:raise HTTPException(422,'El informe supera el límite de almacenamiento de esta versión.')
    return raw,hashlib.sha256(encoded).hexdigest()


def decode_snapshot(row):
    if hashlib.sha256(row.payload.encode()).hexdigest()!=row.sha256:
        raise HTTPException(409,'La integridad del informe no coincide. Requiere revisión antes de consultarlo.')
    try:return json.loads(row.payload)
    except (ValueError,TypeError):raise HTTPException(409,'El informe requiere revisión de integridad.') from None


def released(pid,report_id,version=None):
    query=select(ReportRelease.id).where(ReportRelease.project_id==pid,ReportRelease.report_id==report_id)
    if version is not None:query=query.where(ReportRelease.version==version)
    return exists(query)


def install_report_api(app,db,current_user,allow,uploads):
    def access(pid,user,session,roles=None):
        _,membership=allow(pid,user,session,roles=roles)
        return membership

    def visible_version(pid,report_id,user,session,version=None):
        membership=access(pid,user,session)
        report=session.scalar(select(Report).where(Report.id==report_id,Report.project_id==pid))
        if report is None:raise HTTPException(404,'Informe no disponible.')
        publication=session.scalar(select(ReportRelease).where(ReportRelease.project_id==pid,
                     ReportRelease.report_id==report_id).order_by(ReportRelease.id.desc()).limit(1))
        chosen=version if version is not None else (report.current_version if membership.role in WRITERS else publication.version if publication else None)
        if chosen is None or (membership.role not in WRITERS and not session.scalar(select(released(pid,report_id,chosen)))):
            raise HTTPException(404,'Informe no disponible.')
        row=session.scalar(select(ReportVersion).where(ReportVersion.project_id==pid,
                           ReportVersion.report_id==report_id,ReportVersion.version==chosen))
        if row is None:raise HTTPException(404,'Versión no disponible.')
        return report,row,publication,membership

    def record(report,row,publication,membership,*,session):
        return dict(id=report.id,version=row.version,
                    current_version=report.current_version if membership.role in WRITERS else row.version,
                    published_version=publication.version if publication else None,
                    sha256=row.sha256,created_at=iso_utc(row.created_at),
                    snapshot=decode_snapshot(row),
                    is_released=bool(session.scalar(select(released(report.project_id,report.id,row.version)))))

    @app.get('/api/projects/{pid}/reports')
    def list_reports(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        membership=access(pid,user,session)
        publications=select(ReportRelease.report_id,func.max(ReportRelease.version).label('version')).where(
            ReportRelease.project_id==pid).group_by(ReportRelease.report_id).subquery()
        chosen=Report.current_version if membership.role in WRITERS else publications.c.version
        query=select(Report.id,ReportVersion,publications.c.version).select_from(Report).outerjoin(
            publications,publications.c.report_id==Report.id).join(ReportVersion,and_(
                ReportVersion.report_id==Report.id,ReportVersion.project_id==Report.project_id,
                ReportVersion.version==chosen)).where(Report.project_id==pid)
        reports=session.execute(query.order_by(Report.id.desc()).limit(101)).all()
        items=[]
        for report_id,row,published_version in reports[:100]:
            snapshot=decode_snapshot(row)
            items.append(dict(id=report_id,title=snapshot['title'],version=row.version,
                         published_version=published_version,
                         created_at=iso_utc(row.created_at),citations=len(snapshot['context']['citations']),origin=origin(snapshot),
                         state='draft' if not published_version else 'released' if row.version==published_version else 'updated'))
        published_count=session.scalar(select(func.count(func.distinct(ReportRelease.report_id))).where(ReportRelease.project_id==pid))
        return dict(items=items,published_count=published_count,truncated=len(reports)>100,can_write=membership.role in WRITERS,
                    can_publish=membership.role in PUBLISHERS,role=membership.role)

    @app.post('/api/projects/{pid}/reports')
    def create_report(pid:int,body:ReportInput,user=Depends(current_user),session:Session=Depends(db)):
        access(pid,user,session,WRITERS)
        raw,digest=encode_snapshot(session,pid,body,uploads)
        try:
            report=Report(project_id=pid,created_by=user.id,current_version=1)
            session.add(report);session.flush()
            session.add(ReportVersion(project_id=pid,report_id=report.id,version=1,payload=raw,sha256=digest,created_by=user.id))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='report.create',target=f'{report.id}:v1'))
            session.commit();return dict(id=report.id,version=1,sha256=digest)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'No se pudo guardar el informe; recarga antes de reintentar.') from None

    @app.post('/api/projects/{pid}/reports/{report_id}/versions')
    def revise_report(pid:int,report_id:int,body:ReportRevision,user=Depends(current_user),session:Session=Depends(db)):
        access(pid,user,session,WRITERS)
        existing,_,_,_=visible_version(pid,report_id,user,session)
        if existing.current_version!=body.expected_version:raise HTTPException(409,'El informe cambió. Abre la versión actual antes de guardar.')
        current=session.scalar(select(ReportVersion).where(ReportVersion.project_id==pid,ReportVersion.report_id==existing.id,ReportVersion.version==existing.current_version))
        if decode_snapshot(current).get('mode') in {'local_documentary_briefing_v1','explorer_selection_v1'}:
            raise HTTPException(409,'Este informe conserva sus fuentes. Prepara otro corte o selección desde su pestaña de origen.')
        raw,digest=encode_snapshot(session,pid,body,uploads)
        version=body.expected_version+1
        try:
            claimed=session.execute(update(Report).where(Report.id==report_id,Report.project_id==pid,
                      Report.current_version==body.expected_version).values(current_version=version),
                      execution_options={'synchronize_session':False})
            if claimed.rowcount!=1:
                session.rollback();raise HTTPException(409,'El informe cambió o no está disponible. Vuelve a cargarlo antes de guardar.')
            session.add(ReportVersion(project_id=pid,report_id=report_id,version=version,payload=raw,sha256=digest,created_by=user.id))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='report.version',target=f'{report_id}:v{version}'))
            session.commit();session.expire_all()
            return dict(id=report_id,version=version,sha256=digest)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'Otra persona guardó una versión. Vuelve a cargarla.') from None

    @app.post('/api/projects/{pid}/reports/{report_id}/release')
    def release_report(pid:int,report_id:int,body:ReleaseInput,user=Depends(current_user),session:Session=Depends(db)):
        access(pid,user,session,PUBLISHERS)
        report,row,publication,membership=visible_version(pid,report_id,user,session)
        if report.current_version!=body.expected_version:
            raise HTTPException(409,'Hay una versión nueva. Revísala antes de publicar.')
        decode_snapshot(row)
        try:
            # Serialize release against a concurrent revision without modifying a snapshot.
            claimed=session.execute(update(Report).where(Report.id==report_id,Report.project_id==pid,
                Report.current_version==body.expected_version).values(current_version=body.expected_version),
                execution_options={'synchronize_session':False})
            if claimed.rowcount!=1:
                session.rollback();raise HTTPException(409,'El informe cambió; vuelve a cargarlo.')
            session.add(ReportRelease(project_id=pid,report_id=report_id,version=body.expected_version,published_by=user.id))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='report.release',target=f'{report_id}:v{body.expected_version}'))
            session.commit()
            return dict(id=report_id,published_version=body.expected_version)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'Esta versión ya se publicó o cambió. Recarga el informe.') from None

    @app.get('/api/projects/{pid}/reports/{report_id}')
    def get_report(pid:int,report_id:int,user=Depends(current_user),session:Session=Depends(db)):
        return record(*visible_version(pid,report_id,user,session),session=session)

    @app.get('/api/projects/{pid}/reports/{report_id}/versions')
    def versions(pid:int,report_id:int,user=Depends(current_user),session:Session=Depends(db)):
        report,_,publication,membership=visible_version(pid,report_id,user,session)
        query=select(ReportVersion).where(ReportVersion.project_id==pid,ReportVersion.report_id==report_id)
        if membership.role not in WRITERS:query=query.where(released(pid,report_id,ReportVersion.version))
        rows=session.scalars(query.order_by(ReportVersion.version.desc()).limit(50)).all()
        return [dict(version=row.version,created_at=iso_utc(row.created_at),sha256=row.sha256,
                     title=decode_snapshot(row)['title']) for row in rows]

    @app.get('/api/projects/{pid}/reports/{report_id}/versions/{version}')
    def get_version(pid:int,report_id:int,version:int,user=Depends(current_user),session:Session=Depends(db)):
        return record(*visible_version(pid,report_id,user,session,version),session=session)

    @app.get('/api/projects/{pid}/reports/{report_id}/versions/{version}/export')
    def export_version(pid:int,report_id:int,version:int,user=Depends(current_user),session:Session=Depends(db)):
        result=record(*visible_version(pid,report_id,user,session,version),session=session)
        return JSONResponse(result,headers={'Content-Disposition':f'attachment; filename="NEXO_Informe_{report_id}_v{version}.json"',
                                            'Cache-Control':'no-store'})

    @app.get('/api/projects/{pid}/reports/{report_id}/versions/{version}/document')
    def document(pid:int,report_id:int,version:int,user=Depends(current_user),session:Session=Depends(db)):
        result=record(*visible_version(pid,report_id,user,session,version),session=session)
        from .pulse_models import PlatformBrand
        branding=session.get(PlatformBrand,1);project=session.get(Project,pid)
        html=render_document(result,brand=branding.name if branding else 'NEXO',project=project.name)
        return JSONResponse(dict(format='html',filename=f'NEXO_Informe_{report_id}_v{version}.html',html=html,
            report_id=report_id,version=version,sha256=result['sha256']),headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
