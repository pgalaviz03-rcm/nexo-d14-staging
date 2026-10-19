"""Least privilege, durable uploads, IdP mapping and database-enforced roles."""
from alembic import op
from sqlalchemy import inspect
from app.models import DatasetBlob, UsageCounter

revision='002_nexo_v05'
down_revision='001_nexo_v04'
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    if 'auth_subject' not in {c['name'] for c in inspect(bind).get_columns('users')}:
        op.execute('ALTER TABLE users ADD COLUMN auth_subject VARCHAR(36) UNIQUE')
    DatasetBlob.__table__.create(bind,checkfirst=True)
    UsageCounter.__table__.create(bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    op.execute('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM nexo_app')
    op.execute('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM nexo_app')
    op.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
    op.execute('''DO $$ DECLARE role_name text; BEGIN
        FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
                EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I',role_name);
                EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I',role_name);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I',role_name);
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I',role_name);
            END IF;
        END LOOP;
    END $$''')
    op.execute('GRANT USAGE ON SCHEMA public TO nexo_app')
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    subject="NULLIF(current_setting('nexo.auth_subject',true),'')"
    tables=('users','memberships','projects','datasets','dataset_blobs','section_metrics',
            'feed_sources','news_articles','audit_events','usage_counters')
    for table in tables:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS nexo_project_scope ON {table}')
    op.execute(f'CREATE POLICY nexo_read ON users FOR SELECT TO nexo_app USING (id={actor} OR auth_subject={subject})')
    op.execute(f'CREATE POLICY nexo_read ON memberships FOR SELECT TO nexo_app USING (user_id={actor})')
    for table in tables[2:]:
        project=f'{table}.id' if table=='projects' else f'{table}.project_id'
        member=f'EXISTS (SELECT 1 FROM memberships m WHERE m.project_id={project} AND m.user_id={actor})'
        writer=f"EXISTS (SELECT 1 FROM memberships m WHERE m.project_id={project} AND m.user_id={actor} AND m.role IN ('admin','editor','analyst'))"
        op.execute(f'CREATE POLICY nexo_read ON {table} FOR SELECT TO nexo_app USING ({member})')
        if table in ('datasets','dataset_blobs','feed_sources','news_articles'):
            if table=='feed_sources':
                writer=f"EXISTS (SELECT 1 FROM memberships m WHERE m.project_id={project} AND m.user_id={actor} AND m.role IN ('admin','editor'))"
            check=writer
            if table=='datasets':check+=f' AND uploaded_by={actor}'
            if table=='feed_sources':check+=f' AND created_by={actor}'
            op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({check})')
        if table=='feed_sources':
            # Analysts can refresh existing feeds but cannot create sources.
            refresh=f"EXISTS (SELECT 1 FROM memberships m WHERE m.project_id={project} AND m.user_id={actor} AND m.role IN ('admin','editor','analyst'))"
            op.execute(f'CREATE POLICY nexo_update ON {table} FOR UPDATE TO nexo_app USING ({refresh}) WITH CHECK ({refresh})')
        if table=='audit_events':
            op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({member} AND user_id={actor})')
        if table=='usage_counters':
            op.execute(f'CREATE POLICY nexo_insert ON {table} FOR INSERT TO nexo_app WITH CHECK ({member})')
            op.execute(f'CREATE POLICY nexo_update ON {table} FOR UPDATE TO nexo_app USING ({member}) WITH CHECK ({member})')
    op.execute('GRANT SELECT ON users,memberships,projects,datasets,dataset_blobs,section_metrics,feed_sources,news_articles,audit_events,usage_counters,alembic_version TO nexo_app')
    op.execute('GRANT INSERT ON datasets,dataset_blobs,feed_sources,news_articles,audit_events,usage_counters TO nexo_app')
    op.execute('GRANT UPDATE(status,last_error,last_checked_at) ON feed_sources TO nexo_app')
    op.execute('GRANT UPDATE(used) ON usage_counters TO nexo_app')
    for table in ('datasets','feed_sources','news_articles','audit_events','usage_counters'):
        op.execute(f'GRANT USAGE,SELECT ON SEQUENCE {table}_id_seq TO nexo_app')
    # Prevent associating one project's blob or RSS entry with another project's ID.
    op.execute('ALTER TABLE datasets ADD CONSTRAINT uq_dataset_id_project UNIQUE(id,project_id)')
    op.execute('ALTER TABLE feed_sources ADD CONSTRAINT uq_feed_id_project UNIQUE(id,project_id)')
    op.execute('ALTER TABLE dataset_blobs ADD CONSTRAINT fk_blob_scope FOREIGN KEY(dataset_id,project_id) REFERENCES datasets(id,project_id)')
    op.execute('ALTER TABLE news_articles ADD CONSTRAINT fk_article_feed_scope FOREIGN KEY(feed_id,project_id) REFERENCES feed_sources(id,project_id)')
    op.execute("ALTER TABLE memberships ADD CONSTRAINT valid_role CHECK(role IN ('admin','editor','analyst','viewer'))")
    for table in ('users','projects','datasets','feed_sources','audit_events'):
        op.execute(f'ALTER TABLE {table} ALTER COLUMN created_at SET DEFAULT now()')
    op.execute('ALTER TABLE news_articles ALTER COLUMN ingested_at SET DEFAULT now()')
    op.execute('ALTER TABLE datasets ADD CONSTRAINT uq_dataset_project_digest UNIQUE(project_id,sha256)')
    op.execute('''CREATE FUNCTION public.nexo_bound_dataset() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
            PERFORM pg_advisory_xact_lock(71505,NEW.project_id);
            IF NEW.size_bytes < 1 OR NEW.size_bytes > 12582912 OR
               (SELECT COALESCE(sum(size_bytes),0) FROM public.datasets WHERE project_id=NEW.project_id)+NEW.size_bytes > 262144000 THEN
                RAISE EXCEPTION 'Dataset quota exceeded' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$''')
    op.execute('REVOKE ALL ON FUNCTION public.nexo_bound_dataset() FROM PUBLIC')
    op.execute('CREATE TRIGGER nexo_dataset_limit BEFORE INSERT ON datasets FOR EACH ROW EXECUTE FUNCTION public.nexo_bound_dataset()')
    op.execute('''CREATE FUNCTION public.nexo_bound_articles() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
            PERFORM pg_advisory_xact_lock(71506,NEW.project_id);
            IF (SELECT count(*) FROM public.news_articles WHERE project_id=NEW.project_id) >= 50000 THEN
                RAISE EXCEPTION 'Article quota exceeded' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$''')
    op.execute('REVOKE ALL ON FUNCTION public.nexo_bound_articles() FROM PUBLIC')
    op.execute('CREATE TRIGGER nexo_article_limit BEFORE INSERT ON news_articles FOR EACH ROW EXECUTE FUNCTION public.nexo_bound_articles()')
    op.execute('''CREATE FUNCTION public.nexo_bound_blob() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
            IF octet_length(NEW.content) > 12582912 OR octet_length(NEW.content) < 1 OR
               octet_length(NEW.content) IS DISTINCT FROM (SELECT size_bytes FROM public.datasets WHERE id=NEW.dataset_id AND project_id=NEW.project_id) THEN
                RAISE EXCEPTION 'Blob size mismatch' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$''')
    op.execute('REVOKE ALL ON FUNCTION public.nexo_bound_blob() FROM PUBLIC')
    op.execute('CREATE TRIGGER nexo_blob_limit BEFORE INSERT ON dataset_blobs FOR EACH ROW EXECUTE FUNCTION public.nexo_bound_blob()')
    op.execute('''CREATE FUNCTION public.nexo_bound_feeds() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        BEGIN
            PERFORM pg_advisory_xact_lock(71507,NEW.project_id);
            IF (SELECT count(*) FROM public.feed_sources WHERE project_id=NEW.project_id) >= 5 THEN
                RAISE EXCEPTION 'Feed quota exceeded' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$''')
    op.execute('REVOKE ALL ON FUNCTION public.nexo_bound_feeds() FROM PUBLIC')
    op.execute('CREATE TRIGGER nexo_feed_limit BEFORE INSERT ON feed_sources FOR EACH ROW EXECUTE FUNCTION public.nexo_bound_feeds()')


def downgrade():
    raise RuntimeError('Restaurar respaldo en otro entorno; no ejecutar downgrade destructivo')
