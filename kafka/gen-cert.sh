#!/bin/bash
set -e

BASE_DIR="/home/uii0000/realtime-backend/kafka"

# Validate required configuration files exist
if [[ ! -f "$BASE_DIR/ca.cnf" ]]; then
    echo "Error: CA configuration file not found at $BASE_DIR/ca.cnf"
    exit 1
fi

# Create the certification authority
openssl req -new -nodes \
   -x509 \
   -days 365 \
   -newkey rsa:2048 \
   -keyout $BASE_DIR/ca.key \
   -out $BASE_DIR/ca.crt \
   -config $BASE_DIR/ca.cnf

# Set proper permissions for CA files
chmod 600 $BASE_DIR/ca.key
chmod 644 $BASE_DIR/ca.crt

# Convert CA files to .pem
cat $BASE_DIR/ca.crt $BASE_DIR/ca.key > $BASE_DIR/ca.pem
chmod 600 $BASE_DIR/ca.pem

# Create truststore directory
mkdir -p $BASE_DIR/truststore

# Create truststore and import CA certificate
keytool -keystore $BASE_DIR/truststore/kafka.truststore.jks \
    -alias CARoot \
    -import -file $BASE_DIR/ca.crt \
    -storepass confluent -noprompt

# Save truststore credentials without sudo
echo "confluent" > $BASE_DIR/truststore/truststore_creds
chmod 600 $BASE_DIR/truststore/truststore_creds

# Function to generate broker certificates
generate_broker_certs() {
    local BROKER_NUM=$1
    local BROKER_NAME="kafka${BROKER_NUM}"
    local CREDS_DIR="$BASE_DIR/kafka-${BROKER_NUM}-creds"
    local CONFIG_FILE="$CREDS_DIR/$BROKER_NAME.cnf"
    
    # Validate broker config exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "Error: Broker configuration file not found at $CONFIG_FILE"
        echo "Please create this file before running the script"
        exit 1
    fi

    mkdir -p $CREDS_DIR

    # Create server key and certificate request
    openssl req -new \
        -newkey rsa:2048 \
        -keyout $CREDS_DIR/$BROKER_NAME.key \
        -out $CREDS_DIR/$BROKER_NAME.csr \
        -config $CONFIG_FILE \
        -nodes

    # Set proper permissions for private key
    chmod 600 $CREDS_DIR/$BROKER_NAME.key

    # Sign the certificate with the CA
    openssl x509 -req \
        -days 3650 \
        -in $CREDS_DIR/$BROKER_NAME.csr \
        -CA $BASE_DIR/ca.crt \
        -CAkey $BASE_DIR/ca.key \
        -CAcreateserial \
        -out $CREDS_DIR/$BROKER_NAME.crt \
        -extfile $CONFIG_FILE \
        -extensions v3_req

    # Convert to PKCS12 format
    openssl pkcs12 -export \
        -in $CREDS_DIR/$BROKER_NAME.crt \
        -inkey $CREDS_DIR/$BROKER_NAME.key \
        -chain \
        -CAfile $BASE_DIR/ca.pem \
        -name $BROKER_NAME \
        -out $CREDS_DIR/$BROKER_NAME.p12 \
        -password pass:confluent

    # Set proper permissions for PKCS12 file
    chmod 600 $CREDS_DIR/$BROKER_NAME.p12

    # Create broker keystore and import certificate
    keytool -importkeystore \
        -deststorepass confluent \
        -destkeystore $CREDS_DIR/kafka.$BROKER_NAME.keystore.pkcs12 \
        -srckeystore $CREDS_DIR/$BROKER_NAME.p12 \
        -deststoretype PKCS12 \
        -srcstoretype PKCS12 \
        -noprompt \
        -srcstorepass confluent

    # Set proper permissions for keystore
    chmod 600 $CREDS_DIR/kafka.$BROKER_NAME.keystore.pkcs12

    # Verify keystore
    keytool -list -v \
        -keystore $CREDS_DIR/kafka.$BROKER_NAME.keystore.pkcs12 \
        -storepass confluent

    # Save credentials without sudo
    echo "confluent" > $CREDS_DIR/${BROKER_NAME}_sslkey_creds
    echo "confluent" > $CREDS_DIR/${BROKER_NAME}_keystore_creds
    
    # Set proper permissions for credential files
    chmod 600 $CREDS_DIR/${BROKER_NAME}_sslkey_creds
    chmod 600 $CREDS_DIR/${BROKER_NAME}_keystore_creds
}

# Generate certificates for brokers (update numbers as needed)
BROKERS=(1 2)  # Add more broker numbers if needed: (1 2 3)

for BROKER_NUM in "${BROKERS[@]}"; do
    generate_broker_certs $BROKER_NUM
done

echo "SSL setup complete for brokers: ${BROKERS[@]}"