"""Versioned content analysis queue; client runtime cannot forge AI outputs."""
from alembic import op
from app.analysis_models import ContentAnalysis
revision='007_analysis'
down_revision='006_delivery'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind();ContentAnalysis.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    op.execute('ALTER TABLE content_analyses ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE content_analyses FORCE ROW LEVEL SECURITY')
    op.execute('REVOKE ALL ON content_analyses FROM PUBLIC,nexo_app')
    op.execute("""DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON content_analyses FROM %I',r); END IF;
    END LOOP; END $$""")
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    member=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id=content_analyses.project_id AND m.user_id={actor})'
    writer=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id=content_analyses.project_id AND m.user_id={actor} AND m.role IN (\'admin\',\'editor\',\'analyst\'))'
    clean="state='queued' AND attempts=0 AND sentiment IS NULL AND emotion IS NULL AND mockery IS NULL AND confidence IS NULL AND evidence IS NULL AND provider IS NULL AND model IS NULL AND error_code IS NULL AND completed_at IS NULL AND contract_version='content-v1'"
    op.execute(f'CREATE POLICY nexo_read ON content_analyses FOR SELECT TO nexo_app USING ({member})')
    op.execute(f'CREATE POLICY nexo_insert ON content_analyses FOR INSERT TO nexo_app WITH CHECK ({writer} AND {clean})')
    op.execute('GRANT SELECT,INSERT ON content_analyses TO nexo_app')
    op.execute('REVOKE ALL ON SEQUENCE content_analyses_id_seq FROM PUBLIC')
    op.execute('GRANT USAGE,SELECT ON SEQUENCE content_analyses_id_seq TO nexo_app')

def downgrade():raise RuntimeError('Conservar análisis e historial; restaurar una copia aparte.')
