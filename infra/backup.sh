#!/usr/bin/env bash
#
# Nightly pg_dump → S3, 30-day retention.
#
# The database IS the evidence record. An unbacked-up hash chain is a hash
# chain you will lose. Custom format (-Fc) is used because it supports
# selective restore and parallel restore, both of which matter under pressure.
#
# Cron:  0 2 * * *  /app/infra/backup.sh >> /var/log/troy-backup.log 2>&1

set -euo pipefail

: "${SYNC_DATABASE_URL:?SYNC_DATABASE_URL is required}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"
BACKUP_PREFIX="${BACKUP_PREFIX:-troy/postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
TMPDIR="$(mktemp -d)"
DUMP="${TMPDIR}/troy-${TS}.dump"

cleanup() { rm -rf "${TMPDIR}"; }
trap cleanup EXIT

echo "[backup] ${TS} starting"

pg_dump \
  --dbname="${SYNC_DATABASE_URL}" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-acl \
  --file="${DUMP}"

SIZE=$(stat -c%s "${DUMP}" 2>/dev/null || stat -f%z "${DUMP}")
echo "[backup] dump complete: ${SIZE} bytes"

# A dump smaller than 10KB means the database is empty or the dump failed.
# Uploading it would quietly overwrite good backups with a useless one.
if [ "${SIZE}" -lt 10240 ]; then
  echo "[backup] FATAL: dump suspiciously small (${SIZE} bytes) — aborting"
  exit 1
fi

# Checksum travels with the object so restore can verify integrity.
SHA="$(sha256sum "${DUMP}" | cut -d' ' -f1)"
echo "[backup] sha256=${SHA}"

aws s3 cp "${DUMP}" \
  "s3://${BACKUP_S3_BUCKET}/${BACKUP_PREFIX}/troy-${TS}.dump" \
  --metadata "sha256=${SHA},rows_verified=pending" \
  --storage-class STANDARD_IA

echo "[backup] uploaded"

# Prune beyond retention.
CUTOFF="$(date -u -d "${RETENTION_DAYS} days ago" +%Y%m%d 2>/dev/null \
        || date -u -v-"${RETENTION_DAYS}"d +%Y%m%d)"

aws s3 ls "s3://${BACKUP_S3_BUCKET}/${BACKUP_PREFIX}/" \
| awk '{print $4}' \
| while read -r key; do
    [ -z "${key}" ] && continue
    d="$(echo "${key}" | sed -n 's/troy-\([0-9]\{8\}\)T.*/\1/p')"
    [ -z "${d}" ] && continue
    if [ "${d}" -lt "${CUTOFF}" ]; then
      echo "[backup] pruning ${key}"
      aws s3 rm "s3://${BACKUP_S3_BUCKET}/${BACKUP_PREFIX}/${key}"
    fi
  done

echo "[backup] done"