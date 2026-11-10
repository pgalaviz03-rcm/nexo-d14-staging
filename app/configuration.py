"""Project-local configuration and media contracts; no external calls."""
from datetime import datetime,timezone
from typing import Literal
import base64,hashlib,json,os
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import Field,SecretStr,AwareDatetime,model_validator
from sqlalchemy import ForeignKey,ForeignKeyConstraint,UniqueConstraint,String,Text,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base
from .apify_port import Strict,public_url
from .actors_api import PublicChannel
from .apify_catalog import ApifyProcessInput,ExecutionInput,validate_processes,catalog as apify_catalog

CATALOG={
 'apify':('Apify · escucha y cuentas',['api_token']),
 'generation':('IA · análisis y RAG',['api_key']),
 'embeddings':('Embeddings e índice semántico',['api_key']),
 'email':('Correo electrónico',['api_key']),
 'telegram':('Telegram',['bot_token']),
 'whatsapp':('WhatsApp',['access_token']),
 'database':('Base de datos de nube',['connection_string']),
 'storage':('Archivos y respaldos',['access_key','secret_key']),
}
class IntegrationSetting(Base):
 __tablename__='integration_settings'
 project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),primary_key=True)
 kind:Mapped[str]=mapped_column(String(32),primary_key=True)
 config_json:Mapped[str]=mapped_column(Text,nullable=False)
 secrets_ciphertext:Mapped[str]=mapped_column(Text,default='',nullable=False)
 version:Mapped[int]=mapped_column(default=1,nullable=False)
 updated_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)

class IntegrationInput(Strict):
 provider:str=Field(default='',max_length=100)
 base_url:str=Field(default='',max_length=1500)
 model:str=Field(default='',max_length=120)
 resource_ref:str=Field(default='',max_length=160)
 dataset_ref:str=Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
 account_ref:str=Field(default='',max_length=160)
 max_items:int=Field(default=100,ge=1,le=500,strict=True)
 daily_limit:int=Field(default=0,ge=0,le=100000,strict=True)
 monthly_budget_usd:Literal[0]=0
 secrets:dict[str,SecretStr]=Field(default_factory=dict,max_length=2)
 clear_secrets:bool=False
 expected_version:int=Field(default=0,ge=0,strict=True)
 apify_processes:dict[str,ApifyProcessInput]|None=Field(default=None,max_length=16)
 apify_execution:ExecutionInput|None=None
 @model_validator(mode='after')
 def safe(self):
  validate_processes(self.apify_processes)
  if self.base_url:self.base_url=public_url(self.base_url)
  for value in [self.provider,self.model,self.resource_ref,self.account_ref]:
   if any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('Texto no admitido.')
  if self.clear_secrets and self.secrets:raise ValueError('Elige reemplazar o borrar las credenciales.')
  if any(not 1<=len(v.get_secret_value())<=4000 or '\x00' in v.get_secret_value() for v in self.secrets.values()):raise ValueError('Credencial fuera del tamaño admitido.')
  return self

def secret_cipher():
 explicit=os.getenv('NEXO_INTEGRATIONS_ENCRYPTION_KEY','')
 if explicit:
  try:return Fernet(explicit.encode('ascii'))
  except (ValueError,UnicodeError):raise HTTPException(409,'La clave de cifrado de integraciones necesita revisión.') from None
 if os.getenv('NEXO_ENV','local')!='local':raise HTTPException(409,'Falta la clave independiente de cifrado de integraciones.')
 secret=os.getenv('NEXO_SECRET_KEY','')
 if len(secret)<32:raise HTTPException(409,'Falta la clave privada local de cifrado.')
 return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('nexo.integrations.v1\0'+secret).encode()).digest()))

def integration_record(row,kind):
 config=json.loads(row.config_json) if row else IntegrationInput().model_dump(exclude={'secrets','clear_secrets','expected_version'})
 runtime={}
 if kind=='apify':
  from .apify_runtime import public_execution
  runtime=public_execution(config)
 config={k:v for k,v in config.items() if not k.startswith('_')}
 return dict(kind=kind,name=CATALOG[kind][0],secret_fields=CATALOG[kind][1],settings=config,
  version=row.version if row else 0,credentials_saved=bool(row and row.secrets_ciphertext),
  state='saved_locally' if row else 'not_configured',connection_verified=bool(runtime.get('verified_at')),external_calls=0,runtime_enabled=bool(runtime and runtime['mode']!='paused' and row and row.secrets_ciphertext),
  **({'apify_catalog':apify_catalog(),'execution':runtime} if kind=='apify' else {}))

class MediaOutlet(Base):
 __tablename__='media_outlets'
 id:Mapped[int]=mapped_column(primary_key=True)
 project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False)
 name:Mapped[str]=mapped_column(String(160),nullable=False)
 name_key:Mapped[str]=mapped_column(String(160),nullable=False)
 site_url:Mapped[str]=mapped_column(Text,default='',nullable=False)
 channels_json:Mapped[str]=mapped_column(Text,nullable=False)
 active:Mapped[bool]=mapped_column(default=True,nullable=False)
 version:Mapped[int]=mapped_column(default=1,nullable=False)
 updated_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
 __table_args__=(UniqueConstraint('id','project_id',name='uq_media_outlet_scope'),UniqueConstraint('project_id','name_key',name='uq_media_outlet_name'))

class MediaArticleLink(Base):
 __tablename__='media_article_links'
 id:Mapped[int]=mapped_column(primary_key=True)
 project_id:Mapped[int]=mapped_column(nullable=False)
 media_id:Mapped[int]=mapped_column(nullable=False)
 article_id:Mapped[int]=mapped_column(nullable=False)
 network:Mapped[str]=mapped_column(String(20),nullable=False)
 account_url:Mapped[str]=mapped_column(Text,nullable=False)
 external_id:Mapped[str]=mapped_column(String(200),nullable=False)
 captured_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
 __table_args__=(ForeignKeyConstraint(['media_id','project_id'],['media_outlets.id','media_outlets.project_id'],name='fk_media_article_outlet'),
  ForeignKeyConstraint(['article_id','project_id'],['news_articles.id','news_articles.project_id'],name='fk_media_article_news'),
  UniqueConstraint('project_id','media_id','network','external_id',name='uq_media_article_source'))

class MediaInput(Strict):
 name:str=Field(min_length=2,max_length=160)
 site_url:str=Field(default='',max_length=1500)
 channels:list[PublicChannel]=Field(default_factory=list,max_length=5)
 active:bool=True
 expected_version:int=Field(default=0,ge=0,strict=True)
 @model_validator(mode='after')
 def safe(self):
  self.name=' '.join(self.name.split())
  if len(self.name)<2 or any(ord(c)<32 for c in self.name):raise ValueError('Nombre no admitido.')
  if self.site_url:self.site_url=public_url(self.site_url)
  if any(c.network not in ('facebook','instagram','x','tiktok','youtube') for c in self.channels):raise ValueError('Elige una red social del medio.')
  if len({(c.network,c.url) for c in self.channels})!=len(self.channels):raise ValueError('Hay cuentas repetidas.')
  if not self.site_url and not self.channels:raise ValueError('Registra el sitio o al menos una cuenta del medio.')
  return self

class MediaPost(Strict):
 external_id:str=Field(min_length=1,max_length=200)
 url:str=Field(min_length=10,max_length=1500)
 title:str=Field(min_length=2,max_length=650)
 text:str=Field(default='',max_length=4000)
 published_at:AwareDatetime
 @model_validator(mode='after')
 def safe(self):
  self.url=public_url(self.url)
  if self.external_id=='REEMPLAZAR_ID' or 'REEMPLAZAR_ID' in self.url:raise ValueError('Completa la plantilla con identificadores y enlaces de origen.')
  if not self.title.strip():raise ValueError('Falta el título.')
  return self
class MediaBatch(Strict):
 network:Literal['facebook','instagram','x','tiktok','youtube']
 account_url:str=Field(min_length=10,max_length=1500)
 captured_at:AwareDatetime
 items:list[MediaPost]=Field(min_length=1,max_length=500)
 @model_validator(mode='after')
 def safe(self):
  self.account_url=PublicChannel(network=self.network,url=self.account_url).url
  for p in self.items:
   PublicChannel(network=self.network,url=p.url)
   if p.published_at>self.captured_at:raise ValueError('Publicación posterior a la captura.')
  if len({p.external_id for p in self.items})!=len(self.items):raise ValueError('Identificadores duplicados.')
  return self
