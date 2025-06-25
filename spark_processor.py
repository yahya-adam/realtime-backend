from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.sql.types import *
from pyspark.ml import PipelineModel
import signal
from pyspark.sql.functions import from_json
import os
import time
from pyspark.sql import functions as F

spark = SparkSession.builder \
    .appName("TemperatureDataProcessor") \
    .config("spark.jars.packages", "org.postgresql:postgresql:42.7.3") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:3.5.1") \
    .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.LocalFileSystem") \
    .config("spark.sql.streaming.schemaInference", "true") \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .config("spark.sql.streaming.metricsEnabled", "true") \
    .config("spark.sql.shuffle.partitions", "8") \
    .config("spark.executor.memory", "4g")\
    .config("spark.sql.session.timeZone", "UTC") \
    .config("spark.driver.extraJavaOptions", "-Dlog4j.configuration=file:/opt/bitnami/spark/conf/log4j2.properties -Dlog4j.logLevel=DEBUG") \
    .getOrCreate()

# State store configurations
spark.conf.set(
    "spark.sql.streaming.stateStore.providerClass",
    "org.apache.spark.sql.execution.streaming.state.HDFSBackedStateStoreProvider"
)
spark.conf.set("spark.sql.streaming.stateStore.minDeltasForSnapshot", 1)

# Load model
model_path = "/app/models/temperature_pipeline"
try:
    pipeline_model = PipelineModel.load(model_path)
except Exception as e:
    spark.stop()
    raise RuntimeError(f"Failed to load model: {str(e)}")

# Read truststore password
with open('/app/truststore/truststore_creds', 'r') as f:
    truststore_password = f.read().strip()

# Read from Kafka
kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka1:19093,kafka2:29094") \
    .option("kafka.security.protocol", "SSL") \
    .option("kafka.ssl.truststore.location", "/app/truststore/kafka.truststore.jks") \
    .option("kafka.ssl.truststore.password", truststore_password) \
    .option("subscribe", "test-topic") \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "false") \
    .load()

# Schema definition 
streaming_schema = StructType([
    StructField("timestamp_utc", StringType(), True),
    StructField("timestamp_epoch", DoubleType(), True),
    StructField("temp_f", DoubleType(), True),
    StructField("temp_c", DoubleType(), True),
    StructField("device_id", DoubleType(), True)
])

# Parse and clean
parsed_stream = kafka_df.select(
    F.from_json(
        F.regexp_replace(F.col("value").cast("string"), r"\\/", "/"),  # Remove escapes
        streaming_schema
    ).alias("data")
).select("data.*").na.drop()

# Parse timestamp
parsed_stream = parsed_stream.withColumn(
    "timestamp_utc",
    F.to_timestamp(F.trim(F.col("timestamp_utc")), "d/M/yyyy H:mm")  # Trim whitespace
).filter(F.col("timestamp_utc").isNotNull())  # Filter invalid

# Debug stream
def debug_parsing(df, epoch_id):
    print("=== Raw Kafka Messages ===")
    df.select("value").show(5, truncate=False)
    print("=== Parsed Data ===")
    parsed_df = df.select(
        F.from_json(F.col("value").cast("string"), streaming_schema).alias("data")
    ).select("data.*")
    parsed_df.show(5, truncate=False)

debug_query = kafka_df.writeStream \
    .foreachBatch(debug_parsing) \
    .trigger(processingTime="10 seconds") \
    .start()

# Prediction function
def make_predictions(batch_df, batch_id):
    if not batch_df.isEmpty():
 
        # Model inference
        predictions_df = pipeline_model.transform(batch_df)
        
        # Prepare output
        result_df = predictions_df.select(
            F.col('timestamp_utc').alias("timestamp"),
            F.col('temp_c').alias("actual_temp_c"),
            F.col("prediction").alias("predicted_temp_c")
        ).withColumn("timestamp", F.col("timestamp").cast("timestamp")).filter(F.col("timestamp").isNotNull()) 
       
        # Debug
        print(f"Batch {batch_id} Final Output:")
        result_df.show(5, truncate=False)
        
        def get_postgres_password():
            secret_path = '/run/secrets/postgres_password'
            try:
                with open(secret_path, 'r') as f:
                    return f.read().strip()
            except IOError:
        # Fallback for local testing
               return os.getenv('POSTGRES_PASSWORD', 'default_password')  
                
        # Write to PostgreSQL
        jdbc_url = "jdbc:postgresql://postgresql:5432/taxi_db"
        pg_properties = {
            "user":  "admin",
            "password": get_postgres_password(), # Securely get password
            "driver": "org.postgresql.Driver"
        }
        try:
            result_df.write \
                .format("jdbc") \
                .option("url", jdbc_url) \
                .option("dbtable", "temperature_predictions") \
                .options(**pg_properties) \
                .mode("append") \
                .save()
            print(f"Batch {batch_id} committed")
        except Exception as e:
            print(f"Batch {batch_id} failed: {str(e)}")
            raise e

# Start streaming
checkpoint_dir = "/opt/spark_checkpoints"
os.makedirs(checkpoint_dir, exist_ok=True)
query = parsed_stream.writeStream \
    .foreachBatch(make_predictions) \
    .outputMode("append") \
    .option("checkpointLocation", checkpoint_dir) \
    .trigger(processingTime='5 seconds') \
    .start()

# Shutdown handling
def handle_shutdown(signum, frame):
    print("\nShutting down...")
    query.stop()
    debug_query.stop()
    spark.stop()

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

query.awaitTermination()
# spark.streams.awaitAnyTermination()
# # Single await for main query
# try:
#     query.awaitTermination()
# except Exception as e:
#     print(f"Stream terminated with exception: {str(e)}")
# finally:
#     debug_query.stop()
#     spark.stop()
#     print("Spark session stopped")
