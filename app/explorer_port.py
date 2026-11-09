"""Project evidence contracts; provider results never select tools or accounts."""
from datetime import datetime,timedelta,timezone
from typing import Literal,Annotated,Protocol
from pydantic import Field,model_validator
from .apify_port import Strict
Reference=Annotated[str,Field(pattern=r'^(news|social|document):[1-9][0-9]{0,9}$')]
class ExplorerQuery(Strict):
    q:str=Field(default='',max_length=120)
    kind:Literal['all','news','social','document']='all'
    network:Literal['all','press','facebook','instagram','x','tiktok','youtube','other']='all'
    actor_id:int=Field(default=0,ge=0,strict=True)
    source:str=Field(default='',max_length=200)
    start:datetime|None=None
    end:datetime|None=None
    offset:int=Field(default=0,ge=0,le=1100,strict=True)
    @model_validator(mode='after')
    def window(self):
        self.q=self.q.strip()
        if any(ord(c)<32 for c in self.q):raise ValueError('Revisa el texto de búsqueda.')
        if (self.start is None)!=(self.end is None):raise ValueError('Completa ambas fechas.')
        if self.start is not None:
            if self.start.tzinfo is None or self.end.tzinfo is None:raise ValueError('Incluye zona horaria.')
            self.start=self.start.astimezone(timezone.utc);self.end=self.end.astimezone(timezone.utc)
            if not timedelta(minutes=1)<=self.end-self.start<=timedelta(days=3660):raise ValueError('Periodo no admitido.')
            if self.end>datetime.now(timezone.utc):raise ValueError('El periodo no puede terminar en el futuro.')
        return self
class EvidenceSelection(Strict):
    references:list[Reference]=Field(min_length=1,max_length=8)
    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.references))!=len(self.references):raise ValueError('No repitas fuentes en la selección.')
        return self
class ExplorerReport(EvidenceSelection):
    preview_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    title:str=Field(min_length=3,max_length=140)
    note:str=Field(default='',max_length=2000)
class SemanticEvidenceSearch(Protocol):
    def search(self,*,project_id:int,query:ExplorerQuery,limit:int)->list[Reference]:...
class SemanticSearchUnavailable(RuntimeError):pass
class DisabledSemanticEvidenceSearch:
    def search(self,**kwargs):raise SemanticSearchUnavailable('semantic_search_not_connected')
