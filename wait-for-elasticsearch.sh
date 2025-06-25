#!/bin/bash
set -e

until curl -sf -X GET "http://elasticsearch:9200/_cluster/health?wait_for_status=yellow&timeout=50s" >/dev/null; do
  echo "Waiting for Elasticsearch..."
  sleep 5
done
echo "Elasticsearch ready!"