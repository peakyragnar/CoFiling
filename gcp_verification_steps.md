# GCP Storage Verification - Step by Step Guide

## Step 1: Authenticate with Google Cloud

```bash
# Option A: If you have access to the project
gcloud auth login

# Option B: For application default credentials (needed for Python scripts)
gcloud auth application-default login
```

This will open a browser window. Log in with your Google account that has access to project `sec-ai-466316`.

## Step 2: Set the Project

```bash
gcloud config set project sec-ai-466316
```

## Step 3: Check GCS Bucket

```bash
# List all files in the bucket
gcloud storage ls gs://sec-ai-analyst/

# Check if your file exists
gcloud storage ls gs://sec-ai-analyst/merged_sec_data.json

# Get detailed info about the file (if it exists)
gcloud storage stat gs://sec-ai-analyst/merged_sec_data.json
```

## Step 4: Check BigQuery Tables

```bash
# List datasets
bq ls --project_id=sec-ai-466316

# List tables in sec_data dataset
bq ls --project_id=sec-ai-466316 sec_data

# Check row count in facts table
bq query --project_id=sec-ai-466316 --use_legacy_sql=false \
"SELECT COUNT(*) as total_rows FROM \`sec-ai-466316.sec_data.facts\`"

# Check Tesla data specifically
bq query --project_id=sec-ai-466316 --use_legacy_sql=false \
"SELECT COUNT(*) as tesla_facts, 
        COUNT(DISTINCT segment_dimension) as unique_segments,
        MAX(created_at) as last_upload
 FROM \`sec-ai-466316.sec_data.facts\` 
 WHERE cik = '0001318605'"
```

## Step 5: Alternative - Use Google Cloud Console (Web UI)

If CLI doesn't work, use the web interface:

1. **For GCS:**
   - Go to: https://console.cloud.google.com/storage/browser/sec-ai-analyst?project=sec-ai-466316
   - Look for `merged_sec_data.json`
   - Check the upload date and file size

2. **For BigQuery:**
   - Go to: https://console.cloud.google.com/bigquery?project=sec-ai-466316
   - Navigate to: sec-ai-466316 > sec_data
   - Click on `facts` and `texts` tables
   - Click "PREVIEW" to see sample data
   - Click "DETAILS" to see row count

## Step 6: Troubleshooting Common Issues

### If you get permission errors:
- You need to be added to the project with appropriate roles
- Contact the project owner to grant you access

### If the bucket/dataset doesn't exist:
- The bucket or dataset may not have been created yet
- Check if you're using the correct project ID

### If files/data are missing:
- The upload may have failed silently
- Check if `fetch_sec_facts.py` ran successfully
- Look for error messages in the script output

## What Success Looks Like

When everything is working correctly, you should see:

1. **In GCS:**
   - `merged_sec_data.json` file (~3.6 MB)
   - Upload timestamp matching when you ran the script

2. **In BigQuery facts table:**
   - Multiple rows for Tesla (CIK: 0001318605)
   - 21 unique segment dimensions
   - Recent created_at timestamp

3. **In BigQuery texts table:**
   - At least one row for Tesla
   - Contains full filing text

## Quick Check Commands (after authentication)

```bash
# One-liner to check if file exists in GCS
gcloud storage ls gs://sec-ai-analyst/merged_sec_data.json && echo "✓ File exists in GCS" || echo "✗ File not found in GCS"

# One-liner to check BigQuery Tesla data
bq query --project_id=sec-ai-466316 --use_legacy_sql=false "SELECT CONCAT('Tesla facts: ', CAST(COUNT(*) AS STRING)) FROM \`sec-ai-466316.sec_data.facts\` WHERE cik = '0001318605'"
```