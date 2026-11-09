"""Portable manual review tables and future PostgreSQL least-privilege policies.

Prepared locally; never executed against a cloud project by this module.
"""
from alembic import op
from app.models import Topic,ArticleReview,ReviewTopic,ReviewChange,article_scope_index

revision='003_manual_reviews'
down_revision='002_nexo_v05'
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    article_scope_index.create(bind=bind,checkfirst=True)
    for model in (Topic,ArticleReview,ReviewTopic,ReviewChange):
        model.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    for table in ('topics','article_reviews','review_topics','review_changes'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,nexo_app')
        op.execute(f'''DO $$ DECLARE role_name text; BEGIN
            FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
                EXECUTE format('REVOKE ALL ON {table} FROM %I',role_name);
              END IF;
            END LOOP;
        END $$''')
        member=f'EXISTS (SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor})'
        roles="'admin','editor'" if table=='topics' else "'admin','editor','analyst'"
        writer=f"EXISTS (SELECT 1 FROM memberships m WHERE m.project_id={table}.project_id AND m.user_id={actor} AND m.role IN ({roles}))"
        op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING ({member})')
        own=f' AND created_by={actor}' if table=='topics' else f' AND reviewed_by={actor}' if table=='article_reviews' else f' AND actor_id={actor}' if table=='review_changes' else ''
        op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({writer}{own})')
        if table in ('topics','article_reviews'):
            check=writer+(f' AND reviewed_by={actor}' if table=='article_reviews' else '')
            op.execute(f'CREATE POLICY nexo_update ON {table} FOR UPDATE TO nexo_app USING ({writer}) WITH CHECK ({check})')
        if table=='review_topics':
            op.execute(f'CREATE POLICY nexo_delete ON {table} FOR DELETE TO nexo_app USING ({writer})')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO nexo_app')
    op.execute('GRANT UPDATE(name,name_key,active,version) ON topics TO nexo_app')
    op.execute('GRANT UPDATE(status,note,version,reviewed_by,updated_at) ON article_reviews TO nexo_app')
    op.execute('GRANT DELETE ON review_topics TO nexo_app')
    for table in ('topics','article_reviews','review_changes'):
        op.execute(f'REVOKE ALL ON SEQUENCE {table}_id_seq FROM PUBLIC')
        op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')


def downgrade():
    raise RuntimeError('La reversión requiere una copia en otro entorno; no se borra el historial automáticamente.')
