# SEC Filing Analysis Pipeline - Deployment Guide

## Overview

This guide walks you through deploying the automated SEC filing analysis pipeline that:
- Fetches SEC filings automatically
- Processes and stores data in BigQuery
- Enriches data with AI insights using Gemini
- Creates dynamic financial models in Google Sheets

## Prerequisites

1. **Google Cloud Project**: Access to project `sec-ai-466316`
2. **APIs Enabled**:
   - BigQuery API
   - Cloud Storage API
   - Cloud Functions API
   - Vertex AI API
   - Cloud Scheduler API
   - Pub/Sub API
3. **Authentication**: `gcloud auth login` completed
4. **Tools Installed**: `gcloud`, `bq`, `gsutil`

## Step 1: Initial Setup

### 1.1 Authenticate and Set Project
```bash
gcloud auth login
gcloud config set project sec-ai-466316
gcloud auth application-default login
```

### 1.2 Run Setup Script
```bash
./setup_bigquery.sh
```

This creates:
- BigQuery dataset and tables
- Pub/Sub topics
- Cloud Storage bucket

## Step 2: Deploy Cloud Functions

### 2.1 Deploy All Functions
```bash
./deploy_cloud_functions.sh
```

This deploys:
- `fetch-sec-data`: Triggered daily to fetch new filings
- `process-filing`: Triggered when files land in GCS
- `enrich-with-ai`: Uses Gemini to analyze filings

### 2.2 Verify Deployment
```bash
gcloud functions list
```

## Step 3: Test the Pipeline

### 3.1 Manual Test
```bash
# Test with single company
python3 fetch_sec_facts_v2.py --cik 0001318605 --filing-type 10-Q

# Test batch processing
python3 batch_process_companies.py --workers 3
```

### 3.2 Trigger Cloud Function
```bash
gcloud pubsub topics publish sec-fetch-trigger \
  --message='{"companies":[{"cik":"0001318605","name":"Tesla"}],"filing_type":"10-Q"}'
```

### 3.3 Check BigQuery
```sql
-- Check facts
SELECT COUNT(*) FROM `sec-ai-466316.sec_data.facts`;

-- Check segments
SELECT COUNT(*) FROM `sec-ai-466316.sec_data.segments`;

-- View latest insights
SELECT * FROM `sec-ai-466316.sec_data.ai_insights_view` LIMIT 10;
```

## Step 4: Set Up Google Sheets

### 4.1 Create New Google Sheet
1. Go to Google Sheets
2. Create new spreadsheet
3. Name it "SEC Financial Analysis"

### 4.2 Install Apps Script
1. Extensions → Apps Script
2. Delete default code
3. Copy all files from `apps_script/` directory:
   - `Code.gs`
   - `GeminiIntegration.gs`
   - `CompanyConfig.html`
4. Save project

### 4.3 Connect to BigQuery
1. In Sheets: Data → Data connectors → Connect to BigQuery
2. Select project: `sec-ai-466316`
3. Select dataset: `sec_data`
4. Choose views:
   - `company_summary`
   - `segment_performance`
   - `ai_insights_view`

### 4.4 Enable APIs in Apps Script
1. In Apps Script Editor
2. Services → Add Service
3. Add:
   - BigQuery API
   - Sheets API

### 4.5 Configure Companies
1. Return to Sheet
2. SEC Analysis → Configure Companies
3. Add CIKs and company names
4. Save configuration

## Step 5: Create Financial Model

### 5.1 Build Model
1. SEC Analysis → Build Financial Model
2. This creates:
   - Income statement layout
   - Growth calculations
   - Margin analysis
   - Trend charts

### 5.2 Add Segment Analysis
1. SEC Analysis → Update Segment Analysis
2. Creates pivot tables by:
   - Product/Service
   - Geography
   - Business segment

### 5.3 Generate AI Summary
1. Select data range
2. SEC Analysis → Generate AI Summary
3. Reviews AI-generated insights

## Step 6: Schedule Updates

### 6.1 Cloud Scheduler
Already configured to run daily at 6 AM ET:
```bash
gcloud scheduler jobs list
```

### 6.2 Apps Script Trigger
1. In Apps Script: Triggers → Add Trigger
2. Function: `refreshAllData`
3. Event: Time-driven
4. Type: Day timer
5. Time: 8-9 AM

## Usage Examples

### Using AI Formulas in Sheets
```
=AI("Calculate YoY growth", C4:C5)
=AI("Summarize financial performance", A4:H10)
=AI("What is the revenue trend?", C4:C20)
```

### Manual Data Refresh
```javascript
// In Sheet's script editor
refreshAllData();
buildFinancialModel();
generateAISummary();
```

### Query Examples
```sql
-- Company comparison
SELECT * FROM `sec-ai-466316.sec_data.peer_comparison`
WHERE revenue_tier = 'Top 3';

-- Segment trends
SELECT * FROM `sec-ai-466316.sec_data.segment_performance`
WHERE dimension_axis = 'ProductOrServiceAxis'
  AND period_growth_pct > 10;

-- AI insights
SELECT 
  entity_name,
  health_score,
  key_highlight,
  top_risks
FROM `sec-ai-466316.sec_data.ai_insights_view`
WHERE health_score >= 8;
```

## Monitoring

### Check Pipeline Status
```sql
SELECT * FROM `sec-ai-466316.sec_data.filing_status`
ORDER BY created_at DESC
LIMIT 10;
```

### View Errors
```bash
gcloud functions logs read fetch-sec-data --limit 50
gcloud functions logs read process-filing --limit 50
```

### Cost Monitoring
- BigQuery: ~$5 per TB queried
- Cloud Functions: ~$0.40 per million invocations
- Vertex AI: ~$0.00025 per 1K characters
- Storage: ~$0.02 per GB/month

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```bash
   gcloud auth application-default login
   ```

2. **BigQuery Insert Errors**
   - Check table schema matches data
   - Verify data types (especially numeric)
   - Check for required fields

3. **AI Enrichment Fails**
   - Verify Vertex AI API is enabled
   - Check quotas in Cloud Console
   - Review function logs

4. **Sheets Not Updating**
   - Refresh BigQuery connection
   - Check Apps Script logs
   - Verify permissions

## Next Steps

1. **Add More Companies**: Edit Cloud Scheduler job message
2. **Customize Analysis**: Modify AI prompts in `enrich_with_ai`
3. **Add Visualizations**: Create Looker Studio dashboards
4. **Fine-tune Model**: Train custom Vertex AI model on SEC data
5. **Add Alerts**: Set up Cloud Monitoring for anomalies

## Support

- Check logs: `gcloud logging read`
- BigQuery console: https://console.cloud.google.com/bigquery
- Cloud Functions: https://console.cloud.google.com/functions
- File issues: Update this guide with solutions