from sqlalchemy import text

TABLES = ('users','memberships','projects','datasets','dataset_blobs','section_metrics',
          'feed_sources','news_articles','audit_events','usage_counters',
          'topics','article_reviews','review_topics','review_changes',
          'reports','report_versions','report_releases','platform_grants','platform_brand','pulse_configs','pulse_actors',
          'pulse_batches','pulse_documents','pulse_mentions','pulse_accounts','pulse_rules',
          'content_assessments','briefing_schedules','delivery_jobs','content_analyses','actor_profiles','audience_snapshots','alert_incidents','alert_events','fidelity_captures','fidelity_team_members','fidelity_team_observations','integration_settings','media_outlets','media_article_links')


def check_database(engine):
    with engine.connect() as c:
        role = c.execute(text('SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user')).one()
        if any(role):
            raise RuntimeError('El rol de aplicación tiene privilegios prohibidos')
        if c.execute(text('''SELECT EXISTS(SELECT 1 FROM pg_auth_members
            WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))''')).scalar():
            raise RuntimeError('El rol de aplicación pertenece a otros roles')
        if c.execute(text('SELECT version_num FROM alembic_version')).scalar() != '011_workspace_cloud':
            raise RuntimeError('Migraciones incompletas')
        for table in TABLES:
            row=c.execute(text('''SELECT c.relrowsecurity,c.relforcerowsecurity,
                pg_has_role(current_user,c.relowner,'MEMBER') FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public' AND c.relname=:t'''), {'t':table}).one()
            if not row[0] or not row[1] or row[2]:
                raise RuntimeError('RLS no verificable o aplicación propietaria del esquema')
        for table in ('section_metrics',):
            for privilege in ('INSERT','UPDATE','DELETE'):
                if c.execute(text('SELECT has_table_privilege(current_user,:t,:p)'),{'t':table,'p':privilege}).scalar():
                    raise RuntimeError('El rol de aplicación puede modificar identidad o históricos')
        for table in ('review_changes','report_versions','report_releases','pulse_batches','pulse_accounts','audience_snapshots','alert_incidents','alert_events','fidelity_captures','fidelity_team_observations','media_article_links'):
            for privilege in ('UPDATE','DELETE'):
                if c.execute(text('SELECT has_table_privilege(current_user,:t,:p)'),{'t':table,'p':privilege}).scalar():
                    raise RuntimeError('El rol de aplicación puede reescribir versiones o historial')
        for privilege in ('UPDATE','DELETE'):
            if c.execute(text('SELECT has_table_privilege(current_user,:t,:p)'),{'t':'content_analyses','p':privilege}).scalar():
                raise RuntimeError('El rol de aplicación puede falsificar resultados de IA')
        for table in ('platform_grants','platform_brand'):
            for privilege in ('INSERT','UPDATE','DELETE'):
                if c.execute(text('SELECT has_table_privilege(current_user,:t,:p)'),{'t':table,'p':privilege}).scalar():
                    raise RuntimeError('La aplicación puede alterar la administración de plataforma')
        for table,columns in {'users':('id','email','password_hash','auth_subject'),'projects':('id','slug'),'memberships':('id','project_id','user_id')}.items():
            for column in columns:
                if c.execute(text("SELECT has_column_privilege(current_user,:t,:c,'UPDATE')"),{'t':table,'c':column}).scalar():
                    raise RuntimeError('La aplicación puede reasignar identidades o alcance')
        if c.execute(text("SELECT has_schema_privilege(current_user,'public','CREATE')")).scalar():
            raise RuntimeError('El rol de aplicación puede crear objetos')
        if c.execute(text("""SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid
           WHERE t.tgrelid='public.alert_events'::regclass AND t.tgname='nexo_alert_event_guard'
           AND t.tgenabled='O' AND NOT p.prosecdef AND NOT t.tgisinternal""")).scalar()!=1:
            raise RuntimeError('La continuidad del historial de alertas no está protegida')
