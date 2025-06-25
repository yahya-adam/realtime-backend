from kafka import KafkaProducer
import pandas 
import time
import logging
from threading import Thread
import os
import ssl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def load_properties(filepath):
    """Load Java-style properties file into a dictionary"""
    props = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                props[key.strip()] = value.strip()
    return props

def send_messages(data_chunk, producer, topic):
    """Thread function to send messages"""
    total_sent = 0
    for row in data_chunk.itertuples(index=False):
        msg = pandas.Series(row._asdict()).to_json().encode('utf-8')
        try:
            # Send without waiting for immediate confirmation
            producer.send(topic, msg)
            total_sent += 1
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
    
    # Flush thread's messages at the end
    producer.flush(timeout=60)
    logging.info(f"Thread completed. Sent {total_sent} messages.")

producer = None
try:
    # Read only 1,000,000 rows for testing
    df = pandas.read_csv('temper_data.csv').head(1000000)
    logging.info(f"Loaded {len(df)} rows for processing.")
    
    # Load configuration properties
    config_path = os.getenv('KAFKA_CONFIG', '/etc/kafka/secrets/client-ssl.properties')
    config = load_properties(config_path)
    
    # Create custom SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Configure Kafka producer with optimized settings
    producer = KafkaProducer(
        bootstrap_servers="kafka1:19093,kafka2:29094",
        security_protocol='SSL',
        ssl_context=ssl_context,
        ssl_cafile=config.get('ssl.ca.location'),
        ssl_certfile=config.get('ssl.certificate.location'),
        ssl_keyfile=config.get('ssl.key.location'),
        ssl_password=config.get('ssl.key.password', None),
        acks=1,  # Faster acknowledgment
        retries=10,  # More retry attempts
        linger_ms=100,  # Wait up to 100ms to batch messages
        batch_size=32768,  # Larger batch size (32KB)
        max_block_ms=120000,  # 2 minute timeout for send operations
        request_timeout_ms=60000,  # 1 minute request timeout
        connections_max_idle_ms=300000,  # 5 minute connection timeout
        max_in_flight_requests_per_connection=1,  # Better ordering
        api_version=(2, 6)  # Match broker version
    )
    
    # Split data into two threads
    num_threads = 2  # Reduce thread count
    chunks = [df.iloc[i::num_threads] for i in range(num_threads)]
    
    # Start timing and threads
    start_time = time.time()
    threads = []
    for chunk in chunks:
        thread = Thread(target=send_messages, args=(chunk, producer, 'test-topic'))
        thread.start()
        threads.append(thread)
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    # Report performance
    total_time = time.time() - start_time
    throughput = len(df) / total_time
    logging.info(f"Total time: {total_time:.2f}s | Throughput: {throughput:.2f} msg/s")

except Exception as e:
    logging.error(f"Test failed: {e}")
finally:
    if producer:
        producer.flush(timeout=60)
        producer.close(timeout=30)
    else:
        logging.warning("Producer was never initialized")