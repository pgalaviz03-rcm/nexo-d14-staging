"""Queue local AI work; no public endpoint accepts model results or provider keys."""
from datetime import datetime
from fastapi import Depends
from sqlalchemy.orm import Session
from .pulse_service import window
from .content_analysis import prepare,status
from .apify_port import Strict
from pydantic import AwareDatetime

class AnalysisCut(Strict):
    start:AwareDatetime
    end:AwareDatetime

def install_analysis_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/briefing/analysis')
    def state(pid:int,start:datetime|None=None,end:datetime|None=None,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session);start,end=window(start,end)
        return status(session,pid,start,end)

    @app.post('/api/projects/{pid}/briefing/analysis/prepare')
    def queue(pid:int,body:AnalysisCut,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'});start,end=window(body.start,body.end)
        result=prepare(session,pid,start,end);session.commit();return result
