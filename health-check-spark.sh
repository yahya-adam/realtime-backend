#!/bin/sh
set -e

# Wait for Spark Master to be responsive
until curl -s http://localhost:8080 >/dev/null; do
  echo "Still waiting for Spark UI..."
  sleep 10
done

# Success
exit 0
