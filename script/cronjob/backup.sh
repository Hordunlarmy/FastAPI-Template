#!/bin/bash

set -e

DB_BACKUP_PATH="/app/storage/backups"

mkdir -p "$DB_BACKUP_PATH"
BACKUP_FILE="$DB_BACKUP_PATH/$(date +%F_%T)_backup.sql"

backup_database() {
	PGPASSWORD="$DB_PASSWORD" pg_dump \
		-h "$DB_HOST" -p "$DB_PORT" \
		-U "$DB_USER" \
		-d "$DB_NAME" \
		-F p >"$BACKUP_FILE"

	if [ $? -eq 0 ]; then
		echo "Backup successfully created: $BACKUP_FILE"
	else
		echo "Backup failed"
	fi
}

cleanup_old_backups() {
	# Find and delete backups older than the 10 most recent ones
	ls -1t "$DB_BACKUP_PATH"/*.sql | tail -n +11 | xargs -r rm -f
}

backup_database
cleanup_old_backups
