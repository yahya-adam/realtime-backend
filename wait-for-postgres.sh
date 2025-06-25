#!/bin/bash
set -e

PGUSER=${DB_USER:-admin}  # Default to "admin"
export PGPASSWORD=${DB_PASSWORD}

until pg_isready -h postgresql -U $PGUSER -d taxi_db -t 5; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done
echo "PostgreSQL ready!"