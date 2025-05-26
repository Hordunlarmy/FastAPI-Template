#!/bin/bash

set -e

# Check if Liquibase is installed
if ! command -v liquibase &>/dev/null; then
	echo "❌ Liquibase not found. Make sure it's installed and in PATH."
	exit 1
fi

RUN_GENERATE=true
RUN_UPDATE=true
INIT=false
DROP_DB=false
MASTER_CHANGELOG=/liquibase/changelog/changelog.json
INIT_CHANGELOG=changelog-initial.sql
CURRENT_CHANGELOG=changelog-$(date +%Y%m%d-%H%M%S).sql
SCRIPTS=(/liquibase/schema/init-db.sql /liquibase/schema/triggers.sql /liquibase/schema/init-data.sql /liquibase/schema/"${ENV}"-dump.sql)

wait_for_db() {
	local RETRIES=20
	local WAIT=2

	echo "⏳ Waiting for $LIQ_DB_HOST to be ready..."

	for ((i = 1; i <= RETRIES; i++)); do
		if PGPASSWORD="$LIQ_DB_PASSWORD" psql -h "$LIQ_DB_HOST" -U "$LIQ_DB_USER" -d postgres -c '\q' &>/dev/null; then
			echo "✅ Database is ready!"
			return 0
		fi
		echo "  Attempt $i/$RETRIES: DB not ready yet, retrying in $WAITs..."
		sleep $WAIT
	done

	echo "❌ Database connection timed out after $((RETRIES * WAIT)) seconds."
	exit 1
}

include_changelog_if_valid() {
	local changelog_path=$1

	# Check if jq is installed
	if ! command -v jq &>/dev/null; then
		echo "❌ jq not found. Please install jq to process JSON."
		exit 1
	fi

	# Check if changelog file exists and is non-empty
	if [ ! -f "changelog/$changelog_path" ] || [ ! -s "changelog/$changelog_path" ]; then
		printf "⚠️ Changelog file is missing or empty: %s\n" "$changelog_path"
		return 0
	fi

	# Check if the master changelog is writable
	if [ ! -w "$MASTER_CHANGELOG" ]; then
		echo "❌ Cannot write to master changelog: Permission denied → $MASTER_CHANGELOG"
		exit 1
	fi

	# Check if the changelog is already included
	if jq -e ".databaseChangeLog[] | select(.include.file == \"$changelog_path\")" "$MASTER_CHANGELOG" >/dev/null; then
		printf "ℹ️ Already included: %s\n" "$changelog_path"
		return 0
	fi

	# Add new include to databaseChangeLog array
	tmp_file=$(mktemp)
	jq ".databaseChangeLog += [{ \"include\": { \"file\": \"$changelog_path\", \"relativeToChangelogFile\": true } }]" \
		"$MASTER_CHANGELOG" >"$tmp_file"

	# Verify the new JSON is valid before overwriting
	if jq -e . "$tmp_file" >/dev/null; then
		cat "$tmp_file" >"$MASTER_CHANGELOG"
		printf "📌 Added include to master changelog: %s\n" "$changelog_path"
	else
		echo "❌ Failed to update master changelog: Invalid JSON generated."
		rm "$tmp_file"
		exit 1
	fi

}

for arg in "$@"; do
	case $arg in
	-g | --generate)
		RUN_UPDATE=false
		shift
		;;
	-u | --update)
		RUN_GENERATE=false
		shift
		;;
	--init)
		INIT=true
		RUN_GENERATE=false
		RUN_UPDATE=false
		shift
		;;
	--clean)
		DROP_DB=true
		RUN_GENERATE=false
		RUN_UPDATE=false
		shift
		;;
	esac
done

wait_for_db

if [ "$INIT" = true ]; then
	if [ ! -f "changelog/$INIT_CHANGELOG" ]; then
		liquibase --changelog-file="changelog/$INIT_CHANGELOG" generateChangeLog --includeSchema=true --includeTablespace=true --includeCatalog=true
	else
		echo "⚠️ $INIT_CHANGELOG already exists. Skipping generation."
	fi

	include_changelog_if_valid "$INIT_CHANGELOG"
	liquibase changelogSync
fi

if [ "$RUN_GENERATE" = true ]; then
	printf "🛠️ Creating temporary Postgres database: $LIQ_DB_SNAPSHOT..."
	PGPASSWORD="$LIQ_DB_PASSWORD" psql -h "$LIQ_DB_HOST" -U "$LIQ_DB_USER" -c "CREATE DATABASE $LIQ_DB_SNAPSHOT;"

	printf "\n📝 Applying reference SQL script to temp db...\n"
	for script in "${SCRIPTS[@]}"; do
		if [ -f "$script" ]; then
			printf "  - Applying %s\n" "$script"
			PGPASSWORD="$LIQ_DB_PASSWORD" psql -h "$LIQ_DB_HOST" -U "$LIQ_DB_USER" -d "$LIQ_DB_SNAPSHOT" -f "$script"
		else
			printf "  ⚠️  Skipping missing script: %s\n" "$script"
		fi
	done


	printf "\n🔄 Generating new changelog...\n"
	CHANGELOG_FILE=$CURRENT_CHANGELOG
	liquibase diff-changelog --changelog-file="changelog/$CHANGELOG_FILE"
	include_changelog_if_valid "$CHANGELOG_FILE"

	DROP_DB=true

	printf "\n✅ Liquibase migration ready!\n"
fi

if [ "$RUN_UPDATE" = true ]; then
	printf "\n🚀 Applying database changes...\n"
	if liquibase update; then
		printf "\n✅ Liquibase migration complete!\n"
	else
		printf "\n⚠️ Liquibase update failed — attempting changelogSync instead...\n"
		if liquibase changelogSync; then
			printf "\n✅ changelogSync complete! Schema assumed to be already in place.\n"
		else
			printf "\n❌ changelogSync also failed. Divine intervention may be required.\n"
		fi
	fi
	DROP_DB=true
fi

if [ "$DROP_DB" = true ]; then
	printf "\n🧹 Cleaning up: Dropping temporary database...\n"
	PGPASSWORD="$LIQ_DB_PASSWORD" psql -h "$LIQ_DB_HOST" -U "$LIQ_DB_USER" -c "DROP DATABASE IF EXISTS $LIQ_DB_SNAPSHOT;"
fi
