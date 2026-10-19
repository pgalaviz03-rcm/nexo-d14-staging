#!/usr/bin/env bash
# SOLO base vacía dedicada a recuperación, nunca producción existente.
set -euo pipefail
: "${NEXO_RESTORE_CONFIRM:?Usar RESTORE_TO_EMPTY_ISOLATED_DB}"
test "$NEXO_RESTORE_CONFIRM" = RESTORE_TO_EMPTY_ISOLATED_DB
: "${NEXO_RESTORE_DATABASE:?}" "${PGDATABASE:?}" "${PGHOST:?}" "${PGPASSWORD:?}" "${PGSSLROOTCERT:?}"
test "$PGDATABASE" = "$NEXO_RESTORE_DATABASE"
test "$#" = 2
export PGSSLMODE=verify-full
export PGCONNECT_TIMEOUT=10
existing=$(psql -X -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_tables WHERE schemaname='public'")
test "$existing" = 0
role_exists=$(psql -X -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_roles WHERE rolname='nexo_app'")
test "$role_exists" = 1
age --decrypt --identity "$2" "$1" | pg_restore --exit-on-error --no-owner --no-acl --dbname "$PGDATABASE"
printf '%s\n' 'restored; aplicar deploy/runtime_grants.sql y ejecutar RLS antes de conectar aplicación'
