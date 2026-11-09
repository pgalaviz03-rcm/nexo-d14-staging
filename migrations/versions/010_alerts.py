"""Project findings and immutable review events, without notification dispatch."""
from alembic import op
from app.alert_models import AlertIncident,AlertEvent
revision='010_alerts'
down_revision='009_audience'
branch_labels=None
depends_on=None
def upgrade():
    bind=op.get_bind()
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_pulse_rule_scope ON pulse_rules(id,project_id,actor_id,is_demo)')
    for cls in (AlertIncident,AlertEvent):cls.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    for table in ('alert_incidents','alert_events'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY');op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,nexo_app')
        op.execute(f"""DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON {table} FROM %I',r); END IF;
        END LOOP; END $$""")
        member=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor})'
        writer=f"EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor} AND m.role IN ('admin','editor','analyst'))"
        condition=f'{writer} AND created_by={actor}'
        op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING ({member})')
        op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({condition})')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO nexo_app')
        op.execute(f'REVOKE ALL ON SEQUENCE {table}_id_seq FROM PUBLIC');op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')
    # An invoker trigger can read the ledger through its SELECT policy without
    # recursively embedding the target table in its own INSERT policy.
    op.execute("""CREATE FUNCTION public.nexo_alert_event_guard() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
      DECLARE prior_version integer; prior_state text;
      BEGIN
        PERFORM pg_advisory_xact_lock(7853,NEW.alert_id);
        SELECT e.version,e.status INTO prior_version,prior_state FROM public.alert_events e
          WHERE e.alert_id=NEW.alert_id AND e.project_id=NEW.project_id ORDER BY e.version DESC LIMIT 1;
        IF NEW.version<>COALESCE(prior_version,0)+1 OR NEW.previous_status<>COALESCE(prior_state,'open') THEN
          RAISE EXCEPTION 'Stale alert history' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END; $$""")
    op.execute('REVOKE ALL ON FUNCTION public.nexo_alert_event_guard() FROM PUBLIC')
    op.execute('CREATE TRIGGER nexo_alert_event_guard BEFORE INSERT ON public.alert_events FOR EACH ROW EXECUTE FUNCTION public.nexo_alert_event_guard()')
def downgrade():raise RuntimeError('Conservar incidentes e historial; restaurar en una copia aparte.')
