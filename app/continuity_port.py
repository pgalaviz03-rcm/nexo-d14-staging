"""Input contract: source must supply unique counts and aggregate overlap."""
from datetime import datetime,timedelta,timezone
from typing import Literal,Protocol
import re
from pydantic import Field,model_validator
from .apify_port import Strict,Network
from .actors_api import PublicChannel

CONTRACT='participating-accounts-v1'
class AudienceCapture(Strict):
    actor_id:int=Field(strict=True,gt=0)
    network:Network
    url:str=Field(max_length=2048)
    measurement_id:str=Field(pattern=r'^[a-z][a-z0-9_-]{2,79}$')
    contract_version:Literal['participating-accounts-v1']=CONTRACT
    period_from:datetime
    period_to:datetime
    reference_from:datetime
    reference_to:datetime
    captured_at:datetime
    participants:int=Field(strict=True,ge=0,le=9007199254740991)
    returning:int=Field(strict=True,ge=0,le=9007199254740991)
    reference_participants:int|None=Field(default=None,strict=True,ge=0,le=9007199254740991)

    @model_validator(mode='after')
    def coherent(self):
        self.url=PublicChannel(network=self.network,url=self.url).url
        for name in ('period_from','period_to','reference_from','reference_to','captured_at'):
            value=getattr(self,name)
            if value.tzinfo is None or value.utcoffset() is None:raise ValueError('Incluye zona horaria en todas las fechas.')
            setattr(self,name,value.astimezone(timezone.utc))
        duration=self.period_to-self.period_from
        if not timedelta(minutes=1)<=duration<=timedelta(days=90):raise ValueError('El periodo debe durar entre un minuto y 90 días.')
        if self.reference_to!=self.period_from or self.reference_from!=self.period_from-duration:
            raise ValueError('La referencia debe ser el periodo inmediatamente anterior de igual duración.')
        if self.period_to>self.captured_at:raise ValueError('La captura debe ser posterior al cierre del periodo.')
        if self.returning>self.participants or (self.reference_participants is not None and self.returning>self.reference_participants):
            raise ValueError('El retorno no puede superar ninguna de sus poblaciones.')
        return self

class AudienceBatch(Strict):
    provider:Literal['manual','apify_export']='manual'
    items:list[AudienceCapture]=Field(min_length=1,max_length=100)

class AudienceReader(Protocol):
    def read_aggregates(self,*,network:Network,url:str,start:datetime,end:datetime,measurement_id:str,timeout_seconds:int)->AudienceBatch:...
class AudienceSourceUnavailable(RuntimeError):pass
class DisabledAudienceReader:
    def read_aggregates(self,**kwargs):raise AudienceSourceUnavailable('audience_source_not_connected')

def normalize_audience_export(rows,mapping,*,actor_id,network,url,measurement_id):
    """Explicit aggregate fields only; trusted account context wins. Never reads credentials."""
    fields={'period_from','period_to','reference_from','reference_to','captured_at','participants','returning','reference_participants'}
    if not set(mapping)<=fields or not fields.difference({'reference_participants'})<=set(mapping):raise ValueError('Faltan campos agregados o periodos declarados.')
    if not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}',v) for v in mapping.values()):raise ValueError('Usa campos simples declarados.')
    if not 1<=len(rows)<=100:raise ValueError('Máximo 100 cortes por lote.')
    return AudienceBatch(provider='apify_export',items=[AudienceCapture(actor_id=actor_id,network=network,url=url,
        measurement_id=measurement_id,**{k:row.get(v) for k,v in mapping.items()}) for row in rows])
