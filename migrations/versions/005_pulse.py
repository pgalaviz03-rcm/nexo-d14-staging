"""Local observatory and explicit platform grant; cloud control plane stays off."""
from alembic import op
from app.pulse_models import PlatformGrant,PlatformBrand,PulseConfig,PulseActor,PulseBatch,PulseDocument,PulseMention,PulseAccount,PulseRule

revision='005_pulse'
down_revision='004_reports'
branch_labels=None
depends_on=None
TENANT=('pulse_configs','pulse_actors','pulse_batches','pulse_documents','pulse_mentions','pulse_accounts','pulse_rules')


def upgrade():
    bind=op.get_bind()
    for cls in (PlatformGrant,PlatformBrand,PulseConfig,PulseActor,PulseBatch,PulseDocument,PulseMention,PulseAccount,PulseRule):cls.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    for table in (*TENANT,'platform_grants','platform_brand'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,nexo_app')
        op.execute(f'''DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
          IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON {table} FROM %I',r); END IF;
        END LOOP; END $$''')
        if table=='platform_grants':
            op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING (user_id={actor})')
            op.execute('GRANT SELECT ON platform_grants TO nexo_app');continue
        if table=='platform_brand':
            op.execute('CREATE POLICY nexo_read ON platform_brand FOR SELECT TO nexo_app USING (true)')
            op.execute('GRANT SELECT ON platform_brand TO nexo_app');continue
        member=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor})'
        roles="'admin','editor'" if table in {'pulse_configs','pulse_actors','pulse_rules'} else "'admin','editor','analyst'"
        writer=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor} AND m.role IN ({roles}))'
        own=f' AND created_by={actor}' if table in {'pulse_actors','pulse_batches','pulse_accounts','pulse_rules'} else ''
        if table=='pulse_mentions':own=f' AND (reviewed_by IS NULL OR reviewed_by={actor})'
        op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING ({member})')
        op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({writer}{own})')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO nexo_app')
        if table in {'pulse_configs','pulse_actors','pulse_documents','pulse_mentions','pulse_rules'}:
            check=writer+(f' AND reviewed_by={actor}' if table=='pulse_mentions' else '')
            op.execute(f'CREATE POLICY nexo_update ON {table} FOR UPDATE TO nexo_app USING ({writer}) WITH CHECK ({check})')
        if table in {'pulse_actors','pulse_batches','pulse_documents','pulse_accounts','pulse_rules'}:
            op.execute(f'REVOKE ALL ON SEQUENCE {table}_id_seq FROM PUBLIC')
            op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')
    op.execute('GRANT UPDATE(territory,min_classified,version,connector) ON pulse_configs TO nexo_app')
    op.execute('GRANT UPDATE(name,kind,active,version) ON pulse_actors TO nexo_app')
    op.execute('GRANT UPDATE(views,interactions,collected_at) ON pulse_documents TO nexo_app')
    op.execute('GRANT UPDATE(sentiment,emotion,method,reviewed_by,version) ON pulse_mentions TO nexo_app')
    op.execute('GRANT UPDATE(active) ON pulse_rules TO nexo_app')


def downgrade():raise RuntimeError('Restaurar en un entorno separado; no borrar observaciones automáticamente.')
