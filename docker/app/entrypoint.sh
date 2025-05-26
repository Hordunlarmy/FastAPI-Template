#!/bin/bash

echo "Starting the application..."

if [ "$RELOAD" == "true" ]; then
  echo "Running in development mode with --reload"
  exec uvicorn src.main:app --host 0.0.0.0 --port "$APP_PORT" --workers 4 \
    --timeout-keep-alive 60 --timeout-graceful-shutdown 500 \
    --limit-max-requests 1000 --reload
else
  echo "Running in production mode"
  exec uvicorn src.main:app --host 0.0.0.0 --port "$APP_PORT" --workers 4 \
    --timeout-keep-alive 60 --timeout-graceful-shutdown 500 \
    --limit-max-requests 1000
fi

