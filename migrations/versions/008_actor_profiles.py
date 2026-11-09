"""Add public dossiers without modifying existing actors or observations."""
from alembic import op
from app.actor_models import ActorProfile
revision='008_actor_profiles'
down_revision='007_analysis'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind();ActorProfile.__table__.create(bind=bind,checkfirst=True)
    if bind.dialect.name!='postgresql':return
    op.execute('ALTER TABLE actor_profiles ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE actor_profiles FORCE ROW LEVEL SECURITY')
    op.execute('REVOKE ALL ON actor_profiles FROM PUBLIC,nexo_app')
    op.execute("""DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON actor_profiles FROM %I',r); END IF;
    END LOOP; END $$""")
    actor="NULLIF(current_setting('nexo.actor_id',true),'')::integer"
    member=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id=actor_profiles.project_id AND m.user_id={actor})'
    manager=f'EXISTS(SELECT 1 FROM memberships m WHERE m.project_id=actor_profiles.project_id AND m.user_id={actor} AND m.role IN (\'admin\',\'editor\'))'
    op.execute(f'CREATE POLICY nexo_read ON actor_profiles FOR SELECT TO nexo_app USING ({member})')
    op.execute(f'CREATE POLICY nexo_insert ON actor_profiles FOR INSERT TO nexo_app WITH CHECK ({manager} AND updated_by={actor})')
    op.execute(f'CREATE POLICY nexo_update ON actor_profiles FOR UPDATE TO nexo_app USING ({manager}) WITH CHECK ({manager} AND updated_by={actor})')
    op.execute('GRANT SELECT,INSERT ON actor_profiles TO nexo_app')
    op.execute('GRANT UPDATE(public_role,organization,territory,description,aliases_json,channels_json,version,updated_by,updated_at) ON actor_profiles TO nexo_app')

def downgrade():raise RuntimeError('Conservar fichas e históricos; restaurar aparte.')
