-- SOLO administrador y base NEXO del entorno correcto.
-- Fijar contraseña con \password nexo_app en psql interactivo; no pegarla aquí.
CREATE ROLE nexo_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
-- Si existe, inspeccionar; no repetir CREATE.
-- Alembic 002 aplica grants mínimos. El owner NO es nexo_app.
-- No conceder roles postgres, authenticated, service_role ni otros.
