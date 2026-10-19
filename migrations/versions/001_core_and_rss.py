"""Initial NEXO database with project-scoped RSS tables and PostgreSQL RLS.

Revision ID: 001_nexo_v04
Revises:
"""
from alembic import op
from sqlalchemy import inspect, text
from app.models import Base
revision='001_nexo_v04'
down_revision=None
branch_labels=None
depends_on=None

SCOPE_TABLES=('projects','section_metrics','datasets','feed_sources','news_articles','audit_events')

def upgrade():
    bind=op.get_bind()
    Base.metadata.create_all(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    for table in SCOPE_TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        if table=='projects':
            predicate="EXISTS (SELECT 1 FROM memberships m WHERE m.project_id = projects.id AND m.user_id = NULLIF(current_setting('nexo.actor_id', true), '')::integer)"
        else:
            predicate=f"EXISTS (SELECT 1 FROM memberships m WHERE m.project_id = {table}.project_id AND m.user_id = NULLIF(current_setting('nexo.actor_id', true), '')::integer)"
        # Crucial: INSERT/UPDATE checks both actor membership and project scope; API adds role checks.
        op.execute(f'CREATE POLICY nexo_project_scope ON {table} FOR ALL USING ({predicate}) WITH CHECK ({predicate})')
    op.execute('GRANT USAGE ON SCHEMA public TO nexo_app')
    op.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO nexo_app')
    op.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO nexo_app')


def downgrade():
    raise RuntimeError('Downgrade destructivo no automático. Ver protocolo de archivo/destrucción.')
