#!/bin/bash

BACKUP_SCRIPT_PATH="/usr/local/bin/backup.sh"
BACKUP_CRON="0 2 * * * /bin/bash $BACKUP_SCRIPT_PATH"

# ---- Cron setup ----
if [ "$ENV" == "prod" ]; then
	echo "✅ Production environment detected. Setting up cron job..."

	echo "⏱ Starting cron service..."
	service cron start

	echo "🛠 Setting up backup cron job..."
	(
		crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT_PATH"
		echo "$BACKUP_CRON"
	) | crontab -

	if [ $? -eq 0 ]; then
		echo "✅ Backup cron job set. Runs daily at 2 AM."
	else
		echo "❌ Failed to set backup cron job."
	fi
else
	echo "⚙️  Non-production environment detected. Skipping cron setup."
fi

echo "🚀 Starting the application..."
if [[ "$ENV" == "local" || "$ENV" == "dev" || "$ENV" == "staging" ]]; then
	echo "🔁 Running in development mode with --reload"
	exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1 \
		--timeout-keep-alive 60 --timeout-graceful-shutdown 1 \
		--limit-max-requests 10000 --reload
else
	echo "🏭 Running in production mode"
	exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 \
		--timeout-keep-alive 60 --timeout-graceful-shutdown 500 \
		--limit-max-requests 1000
fi
