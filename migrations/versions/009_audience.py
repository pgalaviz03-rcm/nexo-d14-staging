"""Add immutable aggregate audience snapshots; preserve all existing data."""
from alembic import op
from app.continuity_models import AudienceSnapshot
revision='009_audience'
down_revision='008_actor_profiles'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind();AudienceSnapshot.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    op.execute('ALTER TABLE audience_snapshots ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE audience_snapshots FORCE ROW LEVEL SECURITY')
    op.execute('REVOKE ALL ON audience_snapshots FROM PUBLIC,nexo_app')
    op.execute("""DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON audience_snapshots FROM %I',r); END IF;
    END LOOP; END $$""")
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    member=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id=audience_snapshots.project_id AND m.user_id={actor})'
    writer=f"EXISTS(SELECT 1 FROM memberships m WHERE m.project_id=audience_snapshots.project_id AND m.user_id={actor} AND m.role IN ('admin','editor','analyst'))"
    op.execute(f'CREATE POLICY nexo_read ON audience_snapshots FOR SELECT TO nexo_app USING ({member})')
    op.execute(f'CREATE POLICY nexo_insert ON audience_snapshots FOR INSERT TO nexo_app WITH CHECK ({writer} AND created_by={actor})')
    op.execute('GRANT SELECT,INSERT ON audience_snapshots TO nexo_app')
    op.execute('GRANT USAGE,SELECT ON SEQUENCE audience_snapshots_id_seq TO nexo_app')

def downgrade():raise RuntimeError('Conservar el historial; restaurar en un entorno separado.')
