"""Complete workspace tables and owner-only cloud administration.
No service-role key, security-definer function or public Data API access.
"""
from alembic import op
from sqlalchemy import text,inspect
from app.fidelity import FidelityCapture
from app.fidelity_team import TeamMember,TeamObservation
from app.configuration import IntegrationSetting,MediaOutlet,MediaArticleLink
from app.preflight import TABLES
revision='011_workspace_cloud'
down_revision='010_alerts'
branch_labels=None
depends_on=None
NEW=(FidelityCapture,TeamMember,TeamObservation,IntegrationSetting,MediaOutlet,MediaArticleLink)
ACTOR="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
OWNER=f'EXISTS(SELECT 1 FROM public.platform_grants g WHERE g.user_id={ACTOR} AND g.active)'

def upgrade():
 bind=op.get_bind()
 if 'scope_bindings' not in {c['name'] for c in inspect(bind).get_columns('platform_grants')}:
  op.add_column('platform_grants',__import__('sqlalchemy').Column('scope_bindings',__import__('sqlalchemy').Text(),nullable=False,server_default='{}'))
 for cls in NEW:cls.__table__.create(bind,checkfirst=True)
 if bind.dialect.name!='postgresql':return
 for cls in NEW:
  table=cls.__tablename__
  op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
  op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
  op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC,nexo_app')
  member=f'EXISTS(SELECT 1 FROM public.memberships m WHERE m.project_id={table}.project_id AND m.user_id={ACTOR})'
  read=OWNER if table=='integration_settings' else f'({OWNER}) OR ({member})'
  op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING ({read})')
  own=f' AND updated_by={ACTOR}' if table in {'fidelity_team_members','integration_settings','media_outlets'} else f' AND created_by={ACTOR}' if table=='fidelity_captures' else ''
  op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK (({OWNER}){own})')
  op.execute(f'GRANT SELECT,INSERT ON {table} TO nexo_app')
  if table in {'fidelity_team_members','integration_settings','media_outlets'}:
   op.execute(f'CREATE POLICY nexo_update ON {table} FOR UPDATE TO nexo_app USING ({OWNER}) WITH CHECK (({OWNER}) AND updated_by={ACTOR})')
  if table!='integration_settings':
   op.execute(f'REVOKE ALL ON SEQUENCE {table}_id_seq FROM PUBLIC')
   op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')
 op.execute('GRANT UPDATE(display_name,profiles_json,active,source_sha256,updated_by) ON fidelity_team_members TO nexo_app')
 op.execute('GRANT UPDATE(config_json,secrets_ciphertext,version,updated_by,updated_at) ON integration_settings TO nexo_app')
 op.execute('GRANT UPDATE(name,name_key,site_url,channels_json,active,version,updated_by) ON media_outlets TO nexo_app')
 # Use the self-only grant policy as the root; never reference users/memberships
 # from the grant policy, which would create recursive RLS evaluation.
 known=','.join("'"+name+"'" for name in TABLES)
 policies=bind.execute(text(f"""SELECT c.relname,p.polname,p.polcmd,
  pg_get_expr(p.polqual,p.polrelid) AS qual,pg_get_expr(p.polwithcheck,p.polrelid) AS chk
  FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relname IN ({known}) AND c.relname NOT IN ('platform_grants','platform_brand')""")).mappings().all()
 new_names={cls.__tablename__ for cls in NEW}
 for p in policies:
  table=p['relname'];name=p['polname'];cmd=p['polcmd']
  if table in new_names:continue
  if cmd=='r':
   op.execute(f'ALTER POLICY "{name}" ON "{table}" USING (({p["qual"] or "true"}) OR ({OWNER}))')
  elif table not in {'audit_events','usage_counters'}:
   clauses=[]
   if cmd in {'w','d','*'}:clauses.append(f'USING (({p["qual"] or "true"}) AND ({OWNER}))')
   if cmd in {'a','w','*'}:clauses.append(f'WITH CHECK (({p["chk"] or p["qual"] or "true"}) AND ({OWNER}))')
   if clauses:op.execute(f'ALTER POLICY "{name}" ON "{table}" '+ ' '.join(clauses))
 # The owner can create projects and link existing Supabase identities. The
 # runtime still cannot change subject mappings/passwords, grants or history.
 op.execute(f"CREATE POLICY nexo_owner_insert ON users FOR INSERT TO nexo_app WITH CHECK (({OWNER}) AND auth_subject IS NOT NULL AND password_hash='external-auth-only')")
 op.execute(f'CREATE POLICY nexo_owner_update ON users FOR UPDATE TO nexo_app USING ({OWNER}) WITH CHECK ({OWNER})')
 op.execute(f'CREATE POLICY nexo_owner_insert ON projects FOR INSERT TO nexo_app WITH CHECK ({OWNER})')
 op.execute(f'CREATE POLICY nexo_owner_update ON projects FOR UPDATE TO nexo_app USING ({OWNER}) WITH CHECK ({OWNER})')
 op.execute(f'CREATE POLICY nexo_owner_insert ON memberships FOR INSERT TO nexo_app WITH CHECK ({OWNER})')
 op.execute(f'CREATE POLICY nexo_owner_update ON memberships FOR UPDATE TO nexo_app USING ({OWNER}) WITH CHECK ({OWNER})')
 op.execute(f'CREATE POLICY nexo_global_audit ON audit_events FOR INSERT TO nexo_app WITH CHECK (({OWNER}) AND user_id={ACTOR})')
 op.execute('GRANT INSERT ON users,projects,memberships TO nexo_app')
 op.execute('GRANT UPDATE(active) ON users TO nexo_app')
 op.execute('GRANT UPDATE(name,status) ON projects TO nexo_app')
 op.execute('GRANT UPDATE(role) ON memberships TO nexo_app')
 for table in ('users','projects','memberships'):op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')
 for table in (*TABLES,'alembic_version'):
  op.execute(f"""DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON public.{table} FROM %I',r); END IF;
  END LOOP; END $$""")

def downgrade():raise RuntimeError('Restore a verified backup into a separate environment; no destructive downgrade.')
