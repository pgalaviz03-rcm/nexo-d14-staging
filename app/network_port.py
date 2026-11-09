"""Provider-neutral account snapshots. No SDK, token lookup or network call."""
from datetime import datetime,timezone
from typing import Literal,Protocol
import re
from pydantic import Field,model_validator
from .apify_port import Strict,Network
from .pulse_api import AccountInput
from .actors_api import PublicChannel

COUNTERS=('followers','posts','views','impressions','reach','interactions')

class AccountCapture(AccountInput):
    @model_validator(mode='after')
    def source_contract(self):
        self.captured_at=self.captured_at.astimezone(timezone.utc)
        if self.metrics_from:self.metrics_from=self.metrics_from.astimezone(timezone.utc)
        if self.metrics_to:self.metrics_to=self.metrics_to.astimezone(timezone.utc)
        self.url=PublicChannel(network=self.network,url=self.url).url
        if all(getattr(self,key) is None for key in COUNTERS):raise ValueError('La captura debe contener al menos una métrica observada.')
        if any(getattr(self,key) is not None for key in COUNTERS if key!='followers') and not self.metrics_from:
            raise ValueError('Las métricas de actividad necesitan inicio y fin del periodo.')
        if self.metrics_to and self.metrics_to>self.captured_at:raise ValueError('La captura no puede ser anterior al cierre de sus métricas.')
        return self

class AccountCaptureBatch(Strict):
    provider:Literal['manual','apify_export']='manual'
    items:list[AccountCapture]=Field(min_length=1,max_length=100)

class AccountReader(Protocol):
    def read(self,*,network:Network,url:str,external_id:str,limit:int,timeout_seconds:int)->list[dict]:...

class AccountSourceUnavailable(RuntimeError):pass

class DisabledAccountReader:
    def read(self,**kwargs):raise AccountSourceUnavailable('account_source_not_connected')

def normalize_account_export(items,mapping,*,actor_id,network,url,collected_at):
    """Explicit field map and trusted account context; never trust exported actor IDs."""
    allowed=set(COUNTERS)|{'captured_at','metrics_from','metrics_to'}
    if not set(mapping)<=allowed or not set(mapping).intersection(COUNTERS):raise ValueError('Declara un mapa de métricas admitidas.')
    if not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}',v) for v in mapping.values()):raise ValueError('Solo se admiten campos simples declarados.')
    if not 1<=len(items)<=100:raise ValueError('Máximo 100 capturas por lote.')
    result=[]
    for row in items:
        values={key:row.get(field) for key,field in mapping.items()}
        values.setdefault('captured_at',collected_at)
        result.append(AccountCapture(actor_id=actor_id,network=network,url=url,**values))
    return AccountCaptureBatch(provider='apify_export',items=result)
