"""Apify boundary: offline normalization only. No SDK, token lookup or HTTP."""
from datetime import datetime
from typing import Literal,Protocol
from urllib.parse import urlsplit,parse_qsl
import ipaddress
import re
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,model_validator

Network=Literal['press','facebook','instagram','x','tiktok','youtube','other']
Sentiment=Literal['positive','neutral','negative']
Emotion=Literal['joy','anger','sadness','fear','surprise']


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')


def public_url(value):
    from .listening import normalize_url
    normalized=normalize_url(value)
    p=urlsplit(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443) or p.fragment:
        raise ValueError('Se requiere una URL HTTPS pública sin credenciales ni fragmento.')
    host=p.hostname.lower()
    if any(k.lower() in {'token','access_token','api_key','apikey','password','secret','authorization'} for k,_ in parse_qsl(p.query)):
        raise ValueError('La URL no debe contener claves ni credenciales de API.')
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')) or '.' not in host:
        raise ValueError('El destino no es público.')
    # This validates stored identifiers only. A future HTTP adapter must also
    # resolve/revalidate public IPs and redirects immediately before connecting.
    return normalized


class PublicPost(Strict):
    network:Network
    external_id:str=Field(min_length=1,max_length=200)
    url:str=Field(min_length=10,max_length=2000)
    title:str=Field(min_length=1,max_length=300)
    text:str=Field(default='',max_length=4000)
    published_at:AwareDatetime
    collected_at:AwareDatetime
    actor_ids:list[int]=Field(min_length=1,max_length=20)
    views:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)
    interactions:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)

    @model_validator(mode='after')
    def valid(self):
        public_url(self.url)
        if len(set(self.actor_ids))!=len(self.actor_ids) or any(x<1 for x in self.actor_ids):raise ValueError('Actores duplicados o inválidos.')
        return self


class ImportBatch(Strict):
    provider:Literal['manual','apify_export']='manual'
    dataset_ref:str=Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
    items:list[PublicPost]=Field(min_length=1,max_length=500)


class ConnectorPlan(Strict):
    actor_ref:str=Field(default='',max_length=120,pattern=r'^[A-Za-z0-9_~/-]*$')
    dataset_ref:str=Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
    max_items:int=Field(default=500,ge=1,le=500)
    monthly_budget_usd:int=Field(default=0,ge=0,le=0)
    enabled:Literal[False]=False


class ApifyUnavailable(RuntimeError):pass


class DatasetReader(Protocol):
    def read(self,dataset_ref:str,*,limit:int)->list[dict]:...


class DisabledApifyReader:
    def read(self,dataset_ref:str,*,limit:int=500)->list[dict]:
        raise ApifyUnavailable('Apify permanece desconectado. Usa un lote local normalizado; no se realizan llamadas ni cargos.')


def normalize_export(items:list[dict],mapping:dict,*,network:Network,actor_ids:list[int],collected_at:datetime):
    """Explicit top-level field mapping; arbitrary Actor outputs are not assumed."""
    allowed={'external_id','url','title','text','published_at','views','interactions'}
    if not set(mapping)<=allowed or not {'external_id','url','title','published_at'}<=set(mapping):
        raise ValueError('El mapa debe declarar identificador, URL, título y fecha.')
    if not all(isinstance(v,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}',v) for v in mapping.values()):
        raise ValueError('Solo se admiten campos simples declarados.')
    if not 1<=len(items)<=500:raise ValueError('Se admiten de 1 a 500 registros.')
    return [PublicPost(**{key:item.get(field) for key,field in mapping.items()},network=network,
             actor_ids=actor_ids,collected_at=collected_at) for item in items]
