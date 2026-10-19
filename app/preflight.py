from sqlalchemy import text

TABLES = ('users','memberships','projects','datasets','dataset_blobs','section_metrics',
          'feed_sources','news_articles','audit_events','usage_counters')


def check_database(engine):
    with engine.connect() as c:
        role = c.execute(text('SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user')).one()
        if any(role):
            raise RuntimeError('El rol de aplicación tiene privilegios prohibidos')
        if c.execute(text('''SELECT EXISTS(SELECT 1 FROM pg_auth_members
            WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))''')).scalar():
            raise RuntimeError('El rol de aplicación pertenece a otros roles')
        if c.execute(text('SELECT version_num FROM alembic_version')).scalar() != '002_nexo_v05':
            raise RuntimeError('Migraciones incompletas')
        for table in TABLES:
            row=c.execute(text('''SELECT c.relrowsecurity,c.relforcerowsecurity,
                pg_has_role(current_user,c.relowner,'MEMBER') FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public' AND c.relname=:t'''), {'t':table}).one()
            if not row[0] or not row[1] or row[2]:
                raise RuntimeError('RLS no verificable o aplicación propietaria del esquema')
        for table in ('users','memberships','projects','section_metrics'):
            for privilege in ('INSERT','UPDATE','DELETE'):
                if c.execute(text('SELECT has_table_privilege(current_user,:t,:p)'),{'t':table,'p':privilege}).scalar():
                    raise RuntimeError('El rol de aplicación puede modificar identidad o históricos')
        if c.execute(text("SELECT has_schema_privilege(current_user,'public','CREATE')")).scalar():
            raise RuntimeError('El rol de aplicación puede crear objetos')
