"""Compile SQL for the PGlite test only. NEVER use it to deploy or migrate data."""
import sys,importlib.util,argparse
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from sqlalchemy.schema import CreateTable,CreateIndex
from sqlalchemy.dialects import postgresql
from app.models import Base,article_scope_index

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('work/rls-schema.sql'))
    a=p.parse_args()
    sql=['CREATE ROLE nexo_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;']
    for table in Base.metadata.sorted_tables:
        sql.append(str(CreateTable(table).compile(dialect=postgresql.dialect()))+';')
        sql.extend(str(CreateIndex(i).compile(dialect=postgresql.dialect()))+';' for i in table.indexes)
    sql+=['CREATE TABLE alembic_version(version_num varchar(32) PRIMARY KEY);',"INSERT INTO alembic_version VALUES ('010_alerts');"]
    dummy=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
    for file in ('001_core_and_rss.py','002_cloud_security.py','003_manual_reviews.py','004_reports.py','005_pulse.py','006_delivery.py','007_analysis.py','008_actor_profiles.py','009_audience.py','010_alerts.py'):
        spec=importlib.util.spec_from_file_location('revision',root/'migrations/versions'/file)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        mod.op=SimpleNamespace(get_bind=lambda:dummy,execute=lambda s:sql.append(str(s)+';'))
        mod.inspect=lambda b:SimpleNamespace(get_columns=lambda t:[{'name':'auth_subject'}])
        saved=Base.metadata.create_all
        tables=list(Base.metadata.tables.values())
        saved_create=[t.create for t in tables]
        saved_index_create=article_scope_index.create
        try:
            Base.metadata.create_all=lambda *a,**k:None
            for table in tables:table.create=lambda *a,**k:None
            article_scope_index.create=lambda *a,**k:None
            mod.upgrade()
        finally:
            Base.metadata.create_all=saved
            for table,method in zip(tables,saved_create):table.create=method
            article_scope_index.create=saved_index_create
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text('\n'.join(sql),encoding='utf-8')
    print('SQL de prueba compilado; no aplicarlo a una base existente')
if __name__=='__main__':main()
