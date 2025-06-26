## Manual Setup Instructions

1. **Start foundation services:**
   ```bash
   docker compose up -d zookeeper kafka1 kafka2 postgresql

2. **Wait for healthy status:**
docker ps --format "table {{.Names}}\t{{.Status}}"
# Repeat until all show "healthy"

3. **Create Kafka topic:**
docker exec kafka1 kafka-topics --bootstrap-server kafka1:19093 --command-config /etc/kafka/secrets/client-ssl.properties --create --topic test-topic --partitions 10 --replication-factor 2

4. **Start Spark cluster:**
docker compose up -d spark spark-worker

echo "Waiting for Spark to initialize..."
while [ "$(docker inspect -f {{.State.Health.Status}} spark)" != "healthy" ]; do
  sleep 10
done

5. **Set right permissions for these directories:**
  sudo chmod 777 models  spark_checkpoints  spark_work

6. **Train ML model:**
docker exec spark spark-submit /app/code/train_ml_model.py

7. **Launch streaming processor:**
docker exec -d spark spark-submit /app/code/spark_processor.py

8. **Run kafka producer**
docker exec api python kafka_producer.py

9. **Start remaining services:**
docker compose up -d elasticsearch kibana logstash api

echo "Waiting for Logstash..."
until docker logs logstash 2>&1 | grep -q "Pipelines running"; do
  sleep 5
done

10. **Verify system:**
docker compose logs -f  # Monitor startup
curl http://localhost:8000/health  # API check

11. **Final System Check**
echo "Services Status:"
docker compose ps -a

echo "Kafka Topics:"
docker exec kafka1 kafka-topics --list --bootstrap-server kafka1:19093 \
  --command-config /etc/kafka/secrets/client-ssl.properties