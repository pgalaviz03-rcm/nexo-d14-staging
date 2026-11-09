"""Versioned documentary reports; prepared locally, never auto-applied to cloud."""
from alembic import op
from app.models import Report,ReportVersion,ReportRelease

revision='004_reports'
down_revision='003_manual_reviews'
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    for model in (Report,ReportVersion,ReportRelease):model.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    for table in ('reports','report_versions','report_releases'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,nexo_app')
        op.execute(f'''DO $$ DECLARE role_name text; BEGIN
          FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
              EXECUTE format('REVOKE ALL ON {table} FROM %I',role_name);
            END IF;
          END LOOP;
        END $$''')
        member=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor})'
        writer=f"EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor} AND m.role IN ('admin','editor','analyst'))"
        publisher=f"EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor} AND m.role IN ('admin','editor'))"
        if table=='report_releases':read=member
        else:
            release=f'EXISTS(SELECT 1 FROM report_releases r WHERE r.project_id={table}.project_id AND r.report_id={"reports.id" if table=="reports" else "report_versions.report_id"}'
            if table=='report_versions':release+=' AND r.version=report_versions.version'
            release+=')'
            read=f'({writer} OR ({member} AND {release}))'
        op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING ({read})')
        check=f'{publisher} AND published_by={actor}' if table=='report_releases' else f'{writer} AND created_by={actor}'
        op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({check})')
        if table=='reports':
            op.execute(f'CREATE POLICY nexo_update ON reports FOR UPDATE TO nexo_app USING ({writer}) WITH CHECK ({writer})')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO nexo_app')
        op.execute(f'REVOKE ALL ON SEQUENCE {table}_id_seq FROM PUBLIC')
        op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')
    op.execute('GRANT UPDATE(current_version) ON reports TO nexo_app')


def downgrade():
    raise RuntimeError('Restaurar en otro entorno antes de revertir; no se eliminan informes ni versiones automáticamente.')
