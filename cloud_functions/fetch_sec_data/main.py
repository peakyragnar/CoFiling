"""
Cloud Function: Fetch SEC Data
Triggered by Cloud Scheduler or Pub/Sub to fetch new SEC filings
"""

import functions_framework
import json
import logging
from datetime import datetime, timedelta
from google.cloud import pubsub_v1, storage
import requests
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
PROJECT_ID = os.environ.get('GCP_PROJECT', 'sec-ai-466316')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'sec-ai-analyst')
TOPIC_NAME = os.environ.get('TOPIC_NAME', 'sec-filing-updates')

# SEC API headers
HEADERS = {'User-Agent': os.environ.get('SEC_USER_AGENT', 'mic.b.cunningham@gmail.com')}

@functions_framework.cloud_event
def fetch_sec_data(cloud_event):
    """
    Main entry point for the Cloud Function
    Accepts CloudEvent from Scheduler or Pub/Sub
    """
    
    # Parse event data
    try:
        if hasattr(cloud_event, 'data'):
            data = json.loads(cloud_event.data.get('message', {}).get('data', '{}'))
        else:
            data = {}
        
        companies = data.get('companies', [
            {"cik": "0001318605", "name": "Tesla"},
            {"cik": "0000320193", "name": "Apple"},
            {"cik": "0001652044", "name": "Alphabet"}
        ])
        
        filing_type = data.get('filing_type', '10-Q')
        
        logger.info(f"Processing {len(companies)} companies for {filing_type} filings")
        
        # Process each company
        results = []
        for company in companies:
            result = process_company(company, filing_type)
            results.append(result)
            
            if result['success']:
                # Publish message for downstream processing
                publish_filing_event(result)
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Completed: {successful}/{len(results)} successful")
        
        return {"status": "completed", "results": results}
        
    except Exception as e:
        logger.error(f"Error in fetch_sec_data: {e}")
        return {"status": "error", "error": str(e)}

def process_company(company: dict, filing_type: str) -> dict:
    """Process a single company's latest filing"""
    
    cik = company['cik'].zfill(10)
    
    try:
        # Get company submissions
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        submissions = response.json()
        recent_filings = submissions.get('filings', {}).get('recent', {})
        
        # Find latest filing of requested type
        filing_info = None
        for i, form in enumerate(recent_filings.get('form', [])):
            if form == filing_type:
                filing_info = {
                    'cik': cik,
                    'company_name': company['name'],
                    'entity_name': submissions.get('name', ''),
                    'filing_type': filing_type,
                    'filing_date': recent_filings['filingDate'][i],
                    'accession_number': recent_filings['accessionNumber'][i],
                    'primary_document': recent_filings['primaryDocument'][i]
                }
                break
        
        if not filing_info:
            logger.warning(f"No {filing_type} filing found for {company['name']}")
            return {
                'success': False,
                'company': company['name'],
                'error': f"No {filing_type} filing found"
            }
        
        # Check if we already processed this filing
        if not is_new_filing(filing_info):
            logger.info(f"Filing already processed: {filing_info['accession_number']}")
            return {
                'success': False,
                'company': company['name'],
                'error': "Filing already processed"
            }
        
        # Fetch and store filing metadata
        store_filing_metadata(filing_info)
        
        return {
            'success': True,
            'company': company['name'],
            'filing_info': filing_info
        }
        
    except Exception as e:
        logger.error(f"Error processing {company['name']}: {e}")
        return {
            'success': False,
            'company': company['name'],
            'error': str(e)
        }

def is_new_filing(filing_info: dict) -> bool:
    """Check if filing has already been processed"""
    
    try:
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)
        
        # Check if metadata file exists
        blob_name = f"filings/{filing_info['cik']}/{filing_info['accession_number']}/metadata.json"
        blob = bucket.blob(blob_name)
        
        return not blob.exists()
        
    except Exception as e:
        logger.error(f"Error checking filing status: {e}")
        return True  # Assume new if we can't check

def store_filing_metadata(filing_info: dict):
    """Store filing metadata in GCS"""
    
    try:
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)
        
        # Store metadata
        blob_name = f"filings/{filing_info['cik']}/{filing_info['accession_number']}/metadata.json"
        blob = bucket.blob(blob_name)
        
        metadata = {
            **filing_info,
            'processed_at': datetime.now().isoformat(),
            'status': 'pending_processing'
        }
        
        blob.upload_from_string(
            json.dumps(metadata, indent=2),
            content_type='application/json'
        )
        
        logger.info(f"Stored metadata: {blob_name}")
        
    except Exception as e:
        logger.error(f"Error storing metadata: {e}")
        raise

def publish_filing_event(result: dict):
    """Publish filing event to Pub/Sub for downstream processing"""
    
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
        
        message = {
            'filing_info': result['filing_info'],
            'timestamp': datetime.now().isoformat()
        }
        
        future = publisher.publish(
            topic_path,
            json.dumps(message).encode('utf-8')
        )
        
        future.result()  # Wait for publish to complete
        logger.info(f"Published filing event for {result['filing_info']['accession_number']}")
        
    except Exception as e:
        logger.error(f"Error publishing event: {e}")

# For local testing
if __name__ == "__main__":
    # Simulate cloud event
    class MockCloudEvent:
        data = {
            'message': {
                'data': json.dumps({
                    'companies': [{"cik": "0001318605", "name": "Tesla"}],
                    'filing_type': '10-Q'
                })
            }
        }
    
    result = fetch_sec_data(MockCloudEvent())
    print(json.dumps(result, indent=2))