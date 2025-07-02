## Manual Setup Instructions
1. **ensure all shell files are executable**
  ```bash
  sudo chmod *.sh
2. **Start foundation services:**
   ```bash
   docker compose up -d zookeeper kafka1 kafka2 postgresql

3. **Wait for healthy status:**
docker ps --format "table {{.Names}}\t{{.Status}}"
# Repeat until all show "healthy"

4. **Create Kafka topic:**
docker exec kafka1 kafka-topics --bootstrap-server kafka1:19093 --command-config /etc/kafka/secrets/client-ssl.properties --create --topic test-topic --partitions 10 --replication-factor 2

5. **Start Spark cluster:**
docker compose up -d spark spark-worker

echo "Waiting for Spark to initialize..."
while [ "$(docker inspect -f {{.State.Health.Status}} spark)" != "healthy" ]; do
  sleep 10
done

6. **Set right permissions for these directories:**
  sudo chmod 777 models  spark_checkpoints  spark_work

7. **Train ML model:**
docker exec spark spark-submit /app/code/train_ml_model.py

8. **Launch streaming processor:**
docker exec -d spark spark-submit /app/code/spark_processor.py

9. **Run kafka producer**
docker exec api python kafka_producer.py

10. **Start remaining services:**
docker compose up -d elasticsearch kibana logstash api

echo "Waiting for Logstash..."
until docker logs logstash 2>&1 | grep -q "Pipelines running"; do
  sleep 5
done

11. **Verify system:**
docker compose logs -f  # Monitor startup
curl http://localhost:8000/health  # API check

12. **Final System Check**
echo "Services Status:"
docker compose ps -a

echo "Kafka Topics:"
docker exec kafka1 kafka-topics --list --bootstrap-server kafka1:19093 \
  --command-config /etc/kafka/secrets/client-ssl.properties