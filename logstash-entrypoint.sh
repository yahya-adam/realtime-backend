#!/bin/bash
set -e

# Read password from secret
export DB_PASSWORD=$(cat /run/secrets/postgres_password)

# Wait for dependencies
wait-for-elasticsearch.sh
wait-for-postgres.sh

# Execute original entrypoint
exec /usr/local/bin/docker-entrypoint "$@"
