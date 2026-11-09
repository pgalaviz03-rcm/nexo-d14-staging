"""One-transaction, real-only local-project import. Never copies credentials.
Source author IDs stay in import audit records; target created_by is the importing
operator, not an invented Supabase identity. All original bytes are verified.
"""
import hashlib,json,re
from pathlib import Path
from sqlalchemy import select,insert,func
from sqlalchemy.orm import Session
from app.models import Base,Dataset,Project,AuditEvent,ReportVersion,SectionMetric
from app.library_api import original_bytes
from app import fidelity_team,configuration
from app.workbook_evidence import digest

EXPECTED={'datasets':6,'feed_sources':2,'news_articles':20,'topics':1,'pulse_actors':4,'actor_profiles':4,'pulse_rules':2,'fidelity_team_members':2,'reports':2,'report_versions':3,'report_releases':1}
ORDER=list(EXPECTED)
AUTHOR_FIELDS={'created_by','uploaded_by','updated_by','published_by'}
REFS={'feed_id':'feed_sources','actor_id':'pulse_actors','dataset_id':'datasets','source_dataset_id':'datasets','text_dataset_id':'datasets','document_id':'datasets','report_id':'reports'}

def canon(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def rows(conn,table,pid):
 t=Base.metadata.tables[table];q=select(t).where(t.c.project_id==pid)
 if 'is_demo' in t.c:q=q.where(t.c.is_demo.is_(False))
 return [dict(r) for r in conn.execute(q).mappings()]

def load_source(engine,uploads,source_sha):
 with engine.connect() as c:
  p=c.execute(select(Project.id).where(Project.slug=='d14')).scalar_one()
  data={t:rows(c,t,p) for t in ORDER}
  assert {t:len(v)for t,v in data.items()}==EXPECTED,'Source scope changed; review it before importing.'
  with Session(bind=c) as s:
   blobs={r['id']:original_bytes(s,p,r['id'],uploads)[1] for r in data['datasets']}
  for r in data['report_versions']:assert sha(r['payload'].encode())==r['sha256'],'Source report integrity failed'
  for t in ('pulse_documents','pulse_mentions','pulse_accounts','fidelity_team_observations','fidelity_captures'):
   assert len(rows(c,t,p))==0,'Additional real observations require separate review.'
  return dict(pid=p,data=data,blobs=blobs,sha=source_sha)

def remap(value,maps,source_pid,target_pid):
 if isinstance(value,list):return [remap(x,maps,source_pid,target_pid)for x in value]
 if not isinstance(value,dict):return value
 result={}
 for k,v in value.items():
  if k=='project_id' and v is not None:
   assert v==source_pid,'Foreign project in snapshot';result[k]=target_pid
  elif k in REFS and v is not None:result[k]=maps[REFS[k]][v]
  elif k=='citation' and isinstance(v,str):
   m=re.fullmatch(r'([ND])(\d+)(:.*)?',v);assert m,'Unknown citation contract'
   result[k]=m[1]+str(maps['news_articles' if m[1]=='N' else 'datasets'][int(m[2])])+(m[3]or'')
  else:result[k]=remap(v,maps,source_pid,target_pid)
 if 'workbook_origin' in result and 'content_sha256' in result:
  result['content_sha256']=digest(dict(excerpt=result['excerpt'],origin=result['workbook_origin']))
 return result

def import_project(conn,source,operator):
 pid=conn.execute(select(Project.id).where(Project.slug=='d14',Project.status=='active').with_for_update()).scalar_one()
 marker='local-d14-v1:'+source['sha']
 if conn.execute(select(AuditEvent.id).where(AuditEvent.project_id==pid,AuditEvent.action=='migration.local.complete',AuditEvent.target==marker)).first():
  return dict(already_imported=True,source_sha256=source['sha'],target_project_id=pid)
 hist=conn.execute(select(func.count(),func.sum(SectionMetric.territorial_votes),func.sum(SectionMetric.nominal_list)).where(SectionMetric.project_id==pid)).one()
 assert tuple(hist)==(45,41984,65378),'Target history differs'
 for name in ORDER:
  if name in ('feed_sources','news_articles'):continue
  assert not rows(conn,name,pid),'Target '+name+' is no longer empty; merge needs review'
 maps={t:{}for t in ORDER};counts={};author_records=[]
 for name in ORDER:
  table=Base.metadata.tables[name];added=0
  for original in sorted(source['data'][name],key=lambda r:r.get('id',r.get('actor_id',0))):
   row=dict(original);key='id' if 'id'in table.c else 'actor_id';local_id=row.pop(key)
   authors={k:row[k]for k in AUTHOR_FIELDS if k in row}
   if name in ('feed_sources','news_articles'):
    field='url' if name=='feed_sources' else 'url_hash'
    existing=conn.execute(select(table.c.id).where(table.c.project_id==pid,table.c[field]==row[field])).scalar_one_or_none()
    if existing is not None:maps[name][local_id]=existing;continue
   row['project_id']=pid
   for field in AUTHOR_FIELDS:
    if field in row:row[field]=operator
   for field,target in REFS.items():
    if field in row and row[field]is not None:row[field]=maps[target][row[field]]
   if key=='actor_id':row[key]=maps['pulse_actors'][local_id]
   if name=='datasets':
    row['path']='database'
    if row['detail'].startswith(('xlsx-evidence-v1\n','pdf-evidence-v1\n')):
     prefix,raw=row['detail'].split('\n',1);row['detail']=prefix+'\n'+canon(remap(json.loads(raw),maps,source['pid'],pid))
   if name=='report_versions':
    payload=remap(json.loads(row['payload']),maps,source['pid'],pid)
    payload['import_origin']=dict(source='local-d14',database_sha256=source['sha'],original_version_sha256=original['sha256'],local_author_ids=authors,imported_by=operator)
    row['payload']=canon(payload);row['sha256']=sha(row['payload'].encode());assert len(row['payload'].encode())<=65536
   new_id=conn.execute(insert(table).values(**row).returning(table.c[key])).scalar_one();maps[name][local_id]=new_id;added+=1
   if name=='datasets':
    content=source['blobs'][local_id];assert sha(content)==row['sha256'] and len(content)==row['size_bytes']
    conn.execute(insert(Base.metadata.tables['dataset_blobs']).values(dataset_id=new_id,project_id=pid,content=content))
   attribution=','.join(k+'='+str(v)for k,v in sorted(authors.items()))
   target=source['sha']+'|'+name+'|'+str(local_id)+'>'+str(new_id)+'|'+attribution
   assert len(target)<=160
   conn.execute(insert(AuditEvent).values(project_id=pid,user_id=operator,action='migration.local.row',target=target))
   author_records.append(dict(table=name,source_id=local_id,target_id=new_id,local_authors=authors))
  counts[name]=added
 verify(conn,source,pid,maps)
 conn.execute(insert(AuditEvent).values(project_id=pid,user_id=operator,action='migration.local.complete',target=marker))
 return dict(already_imported=False,source_sha256=source['sha'],target_project_id=pid,inserted=counts,maps=maps,provenance=author_records,history_unchanged=True,original_bytes_verified=True,credentials_copied=False,demo_rows_copied=0)

def verify(conn,source,pid,maps):
 for old,new in maps['datasets'].items():
  t=Base.metadata.tables['dataset_blobs'];raw=conn.execute(select(t.c.content).where(t.c.project_id==pid,t.c.dataset_id==new)).scalar_one()
  assert bytes(raw)==source['blobs'][old]
 for row in rows(conn,'report_versions',pid):
  assert sha(row['payload'].encode())==row['sha256'];obj=json.loads(row['payload']);assert obj['import_origin']['database_sha256']==source['sha']
  def check(x):
   if isinstance(x,list):
    for y in x:check(y)
   if isinstance(x,dict):
    if x.get('kind')=='news' and 'citation'in x:assert int(x['citation'][1:])in maps['news_articles'].values()
    if 'project_id'in x:assert x['project_id']==pid
    for k,v in x.items():
     if k in REFS and v is not None:assert v in maps[REFS[k]].values()
     check(v)
  check(obj)
 for t in ('pulse_documents','pulse_mentions','pulse_accounts','fidelity_team_observations','fidelity_captures'):assert not rows(conn,t,pid)
 for name,count in EXPECTED.items():
  if name=='news_articles':continue
  assert len(rows(conn,name,pid))==count
 assert tuple(conn.execute(select(func.count(),func.sum(SectionMetric.territorial_votes),func.sum(SectionMetric.nominal_list)).where(SectionMetric.project_id==pid)).one())==(45,41984,65378)
