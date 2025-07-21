#!/bin/bash
# Set up BigQuery tables and views

PROJECT_ID="sec-ai-466316"
DATASET_ID="sec_data"

echo "Setting up BigQuery for SEC Filing Analysis..."

# Create dataset if it doesn't exist
echo "1. Creating dataset..."
bq mk --dataset --location=US --description="SEC filing data with AI enrichment" \
  $PROJECT_ID:$DATASET_ID

# Create tables
echo "2. Creating tables..."
bq query --use_legacy_sql=false < bigquery/schema.sql

# Create views
echo "3. Creating views with ML functions..."
bq query --use_legacy_sql=false < bigquery/views.sql

# Create Pub/Sub topics
echo "4. Creating Pub/Sub topics..."
gcloud pubsub topics create sec-fetch-trigger
gcloud pubsub topics create sec-filing-updates
gcloud pubsub topics create sec-filing-ai-enrichment

# Create GCS bucket
echo "5. Creating Cloud Storage bucket..."
gsutil mb -p $PROJECT_ID -l US gs://sec-ai-analyst/

echo "Setup complete!"