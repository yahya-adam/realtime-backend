# Real-Time Backend Setup

## Manual setup (alternative) for step-by-step instructions
./docs/MANUAL_SETUP.md

## Recommended Method: Quick Start
## run the services
1. docker-compose up -d --build
2. docker exec -it spark spark-submit /app/code/train_ml_model.py
3. docker exec -it spark spark-submit /app/code/spark_processor.py
4. docker exec -it api python kafka_producer.py
5. docker exec -it postgresql psql -U admin -d taxi_db
6. docker compose logs -f logstash
