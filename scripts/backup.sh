#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${NEXO_BACKUP_BUCKET:?}" "${NEXO_BACKUP_PREFIX:?}" "${NEXO_BACKUP_RECIPIENT:?}"
: "${PGHOST:?}" "${PGUSER:?}" "${PGPASSWORD:?}" "${PGSSLROOTCERT:?}"
export PGSSLMODE=verify-full
export PGCONNECT_TIMEOUT=10
tmp=$(mktemp -d)
trap 'rm -f "$tmp/db.dump.age" "$tmp/db.dump.age.sha256"; rmdir "$tmp"' EXIT
name="$(date -u +%Y%m%dT%H%M%SZ).dump.age"
pg_dump --format=custom --no-owner --no-acl --schema=public \
  | age --recipient "$NEXO_BACKUP_RECIPIENT" --output "$tmp/db.dump.age"
test -s "$tmp/db.dump.age"
(cd "$tmp" && sha256sum db.dump.age > db.dump.age.sha256)
aws s3 cp "$tmp/db.dump.age" "s3://$NEXO_BACKUP_BUCKET/$NEXO_BACKUP_PREFIX/$name" --only-show-errors
aws s3 cp "$tmp/db.dump.age.sha256" "s3://$NEXO_BACKUP_BUCKET/$NEXO_BACKUP_PREFIX/$name.sha256" --only-show-errors
printf '%s\n' 'backup_uploaded; verificar con restauración en entorno aislado'
