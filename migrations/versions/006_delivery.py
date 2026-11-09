"""Human piece labels, private preferences and a simulation-only outbox."""
from alembic import op
from app.delivery_models import ContentAssessment,BriefingSchedule,DeliveryJob
revision='006_delivery'
down_revision='005_pulse'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    for cls in (ContentAssessment,BriefingSchedule,DeliveryJob):cls.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    for table in ('content_assessments','briefing_schedules','delivery_jobs'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,nexo_app')
        op.execute(f'''DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON {table} FROM %I',r); END IF; END LOOP; END $$''')
        member=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor})'
        if table=='content_assessments':
            writer=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor} AND m.role IN (\'admin\',\'editor\',\'analyst\'))'
            read=member;insert=writer+f' AND reviewed_by={actor}'
            columns='source_title,source_body,source_url,source_sha256,sentiment,emotion,mockery,reviewed_by,version,updated_at'
            update_check=insert
        else:
            read=member+f' AND user_id={actor}';writer=read;insert=read
            columns='channel,frequency,local_time,timezone,weekday,lookback_days,enabled,destination_ciphertext,version,updated_at' if table=='briefing_schedules' else 'state'
            update_check=read if table=='briefing_schedules' else read+" AND state='cancelled'"
            if table=='delivery_jobs':
                insert+=" AND is_simulation AND state IN ('waiting_review','blocked_provider','blocked_recipient')"
                insert+=f' AND (report_id IS NULL OR EXISTS(SELECT 1 FROM report_releases r WHERE r.project_id={table}.project_id AND r.report_id={table}.report_id AND r.version={table}.report_version))'
        op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING ({read})')
        op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({insert})')
        op.execute(f'CREATE POLICY nexo_update ON {table} FOR UPDATE TO nexo_app USING ({writer}) WITH CHECK ({update_check})')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO nexo_app')
        op.execute(f'GRANT UPDATE({columns}) ON {table} TO nexo_app')
        if table!='briefing_schedules':
            op.execute(f'REVOKE ALL ON SEQUENCE {table}_id_seq FROM PUBLIC')
            op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')

def downgrade():raise RuntimeError('Restaurar aparte; no borrar preferencias, revisiones o historial automáticamente.')
