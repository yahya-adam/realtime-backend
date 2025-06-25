from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.sql.types import *
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import RegressionEvaluator
import os
import shutil


spark = SparkSession.builder \
    .appName("TemperatureDataProcessor") \
    .config("spark.jars.packages", "org.postgresql:postgresql:42.7.3")\
    .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.LocalFileSystem") \
    .config("spark.hadoop.fs.file.impl.disable.cache", "true") \
    .getOrCreate()

#schema
trainning_schema =  StructType([
    StructField("timestamp_utc", StringType(), True),
    StructField("timestamp_epoch", DoubleType(), True),
    StructField("temp_f", DoubleType(), True),
    StructField("temp_c", DoubleType(), True),
    StructField("device_id", DoubleType(), True)  
])

df=spark.read.csv("temperature_update.csv", header=True, schema=trainning_schema)
df.printSchema()
print(df.columns)

# # # Split raw data
train_data, test_data= df.randomSplit([0.90, 0.10])

#  #handling categorical values & preparing for ML
# #assembling independent features
feature_columns=["timestamp_epoch","temp_f","device_id"]
assembler= VectorAssembler(
    inputCols= feature_columns,
    outputCol= "features",
    handleInvalid="keep"
 )
# #create a Model
regressor= LinearRegression(
    featuresCol="features",
    labelCol='temp_c',
    regParam=0.1
)

# Pipeline Integration: Preprocessing steps (assembler, regressor)
# Define pipeline stages
pipeline = Pipeline(stages=[assembler,regressor])

pipeline_model= pipeline.fit(train_data)

test_predictions = pipeline_model.transform(test_data)
evaluator = RegressionEvaluator(labelCol='temp_c', metricName="rmse")
rmse = evaluator.evaluate(test_predictions)
print(f"RMSE: {rmse}")

# #saving mode;
model_path = "/app/models/temperature_pipeline"

# Delete existing model if it exists
# if os.path.exists(model_path):
#     shutil.rmtree(model_path)
#     print(f"Deleted existing model directory: {model_path}")
# directory creation
os.makedirs(os.path.dirname(model_path), exist_ok=True)

# Save model
pipeline_model.write().overwrite().save(model_path)
