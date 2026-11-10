"""Local development routes, using the established auth/project dependencies."""
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func,select
from sqlalchemy.orm import Session

from .integration_ports import (connection_catalog,DisabledGeneration,GenerationUnavailable,
                                LocalDocumentarySummary)
from .evidence_search import retrieve_context
from .models import Dataset,NewsArticle,SectionMetric,AuditEvent


class ContextRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=2,max_length=240)
    limit:int=Field(default=5,ge=1,le=8)
    source_kind:str='all'
    days:int=0
    document_id:int|None=Field(default=None,ge=1)


def install_workspace_api(app,db,current_user,allow,uploads):
    from .client_access import install_client_access,read_membership
    # A minimal standalone route harness may not have a database factory.
    if hasattr(app.state,'SessionLocal'):install_client_access(app,current_user)
    allow=read_membership(allow)
    from .configuration_api import install_configuration_api
    install_configuration_api(app,db,current_user,allow)
    from .library_api import install_library_api
    install_library_api(app,db,current_user,allow,uploads)
    from .workbook_api import install_workbook_api
    install_workbook_api(app,db,current_user,allow,uploads)
    from .account_audit import install_account_audit_api
    install_account_audit_api(app,db,current_user,allow)
    from .explorer_api import install_explorer_api
    install_explorer_api(app,db,current_user,allow,uploads)
    from .alert_api import install_alert_api
    install_alert_api(app,db,current_user,allow)
    from .continuity_api import install_continuity_api
    install_continuity_api(app,db,current_user,allow)
    from .network_api import install_network_api
    install_network_api(app,db,current_user,allow)
    from .actors_api import install_actors_api
    install_actors_api(app,db,current_user,allow)
    from .analysis_api import install_analysis_api
    install_analysis_api(app,db,current_user,allow)
    from .delivery_api import install_delivery_api
    from .content_assessment_api import install_assessment_api
    install_delivery_api(app,db,current_user,allow)
    install_assessment_api(app,db,current_user,allow)
    from .briefing_api import install_briefing_api
    install_briefing_api(app,db,current_user,allow)
    from .report_api import install_report_api
    install_report_api(app,db,current_user,allow,uploads)
    from .pulse_api import install_pulse_api
    from .platform_api import install_platform_api
    install_pulse_api(app,db,current_user,allow)
    install_platform_api(app,db,current_user)
    from .refresh_api import install_refresh_api
    if hasattr(app.state,"SessionLocal"):
        install_refresh_api(app,db,current_user,allow)
    @app.get('/api/projects/{pid}/workspace')
    def status(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        return dict(environment=__import__('os').getenv('NEXO_ENV','local'),connections=connection_catalog(),
                    counts={name:session.scalar(select(func.count(model.id)).where(model.project_id==pid,
                            ~Dataset.detail.startswith('pdf-evidence-v1\n'),~Dataset.detail.startswith('xlsx-evidence-v1\n')) if model is Dataset
                            else select(func.count(model.id)).where(model.project_id==pid))
                            for name,model in (('news',NewsArticle),('documents',Dataset),('historical_sections',SectionMetric))},
                    outgoing_connections_enabled=False,generation_enabled=False,
                    scope='Datos del proyecto; no incluye los ejemplos de la maqueta Atalaya.')

    @app.post('/api/projects/{pid}/knowledge/context')
    def context(pid:int,body:ContextRequest,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        try:
            packet=retrieve_context(session,pid,body.question,uploads,limit=body.limit,
                                    source_kind=body.source_kind,days=body.days,document_id=body.document_id)
        except ValueError as exc:raise HTTPException(422,str(exc))
        # Store counts only: no question, source text, file path or credential.
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='knowledge.context',
                               target='citations:'+str(len(packet['citations']))))
        session.commit()
        return packet

    @app.post('/api/projects/{pid}/knowledge/answer')
    def answer(pid:int,body:ContextRequest,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        try:DisabledGeneration().answer({})
        except GenerationUnavailable as exc:raise HTTPException(409,str(exc))

    @app.post('/api/projects/{pid}/knowledge/critical-audit')
    def documentary_digest(pid:int,body:ContextRequest,user=Depends(current_user),session:Session=Depends(db)):
        # Legacy incoming URL retained for UI compatibility. This is an extractive
        # dossier, not an automatic fact check or a political message evaluator.
        allow(pid,user,session)
        try:
            packet=retrieve_context(session,pid,body.question,uploads,limit=body.limit,
                                    source_kind=body.source_kind,days=body.days,document_id=body.document_id)
        except ValueError as exc:raise HTTPException(422,str(exc))
        result=LocalDocumentarySummary().answer(packet)
        # Do not persist the question or source excerpts in a cache or audit log.
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='knowledge.documentary_digest',
                               target='citations:'+str(len(packet['citations']))))
        session.commit()
        return result
