#!/bin/bash

echo "Starting the application..."
exec uvicorn main:app --host 0.0.0.0 --port "$PORT" --workers 4 \
	--timeout-keep-alive 60 --timeout-graceful-shutdown 500 \
	--limit-max-requests 1000
