#!/bin/bash
# Deploy Cloud Functions for SEC Filing Pipeline

PROJECT_ID="sec-ai-466316"
REGION="us-central1"

echo "Deploying Cloud Functions for SEC Filing Pipeline..."

# Deploy fetch_sec_data function
echo "1. Deploying fetch_sec_data function..."
gcloud functions deploy fetch-sec-data \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=cloud_functions/fetch_sec_data \
  --entry-point=fetch_sec_data \
  --trigger-topic=sec-fetch-trigger \
  --env-vars-file=.env.yaml \
  --memory=512MB \
  --timeout=300s \
  --max-instances=10

# Deploy process_filing function
echo "2. Deploying process_filing function..."
gcloud functions deploy process-filing \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=cloud_functions/process_filing \
  --entry-point=process_filing \
  --trigger-resource=sec-ai-analyst \
  --trigger-event=google.storage.object.finalize \
  --env-vars-file=.env.yaml \
  --memory=1GB \
  --timeout=540s \
  --max-instances=20

# Deploy enrich_with_ai function
echo "3. Deploying enrich_with_ai function..."
gcloud functions deploy enrich-with-ai \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=cloud_functions/enrich_with_ai \
  --entry-point=enrich_with_ai \
  --trigger-topic=sec-filing-ai-enrichment \
  --env-vars-file=.env.yaml \
  --memory=2GB \
  --timeout=540s \
  --max-instances=5

# Create Cloud Scheduler job
echo "4. Creating Cloud Scheduler job..."
gcloud scheduler jobs create pubsub sec-daily-fetch \
  --schedule="0 6 * * *" \
  --topic=sec-fetch-trigger \
  --message-body='{"companies":[{"cik":"0001318605","name":"Tesla"},{"cik":"0000320193","name":"Apple"},{"cik":"0001652044","name":"Alphabet"}],"filing_type":"10-Q"}' \
  --time-zone="America/New_York"

echo "Deployment complete!"