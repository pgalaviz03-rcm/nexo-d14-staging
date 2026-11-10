"""Shared project refresh history, owner writes and member reads."""
from alembic import op
from app.refresh_models import ProjectRefreshRun
revision='012_project_refresh'
down_revision='011_workspace_cloud'
branch_labels=None
depends_on=None
SQL="""
ALTER TABLE public.project_refresh_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_refresh_runs FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.project_refresh_runs FROM PUBLIC,nexo_app;
CREATE POLICY nexo_read ON public.project_refresh_runs FOR SELECT TO nexo_app USING (
 EXISTS(SELECT 1 FROM public.platform_grants g WHERE g.user_id=NULLIF(current_setting('nexo.actor_id',true),'')::integer AND g.active)
 OR EXISTS(SELECT 1 FROM public.memberships m WHERE m.project_id=project_refresh_runs.project_id AND m.user_id=NULLIF(current_setting('nexo.actor_id',true),'')::integer));
CREATE POLICY nexo_insert ON public.project_refresh_runs FOR INSERT TO nexo_app WITH CHECK (
 requested_by=NULLIF(current_setting('nexo.actor_id',true),'')::integer AND EXISTS(SELECT 1 FROM public.platform_grants g WHERE g.user_id=NULLIF(current_setting('nexo.actor_id',true),'')::integer AND g.active));
CREATE POLICY nexo_update ON public.project_refresh_runs FOR UPDATE TO nexo_app USING (
 EXISTS(SELECT 1 FROM public.platform_grants g WHERE g.user_id=NULLIF(current_setting('nexo.actor_id',true),'')::integer AND g.active)) WITH CHECK (
 EXISTS(SELECT 1 FROM public.platform_grants g WHERE g.user_id=NULLIF(current_setting('nexo.actor_id',true),'')::integer AND g.active));
GRANT SELECT,INSERT ON public.project_refresh_runs TO nexo_app;
GRANT UPDATE(status,active_key,started_at,finished_at,result_json) ON public.project_refresh_runs TO nexo_app;
REVOKE ALL ON SEQUENCE public.project_refresh_runs_id_seq FROM PUBLIC;
GRANT USAGE,SELECT ON SEQUENCE public.project_refresh_runs_id_seq TO nexo_app;
DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON public.project_refresh_runs FROM %I',r); END IF;
END LOOP; END $$;
"""
def upgrade():
 bind=op.get_bind();ProjectRefreshRun.__table__.create(bind,checkfirst=True)
 if bind.dialect.name=='postgresql':op.execute(SQL)
def downgrade():raise RuntimeError('No destructive downgrade; restore in an isolated environment.')
