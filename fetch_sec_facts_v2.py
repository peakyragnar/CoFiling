#!/usr/bin/env python3
"""
SEC Facts Fetcher v2 - Enhanced with error handling and proper BigQuery integration
Fetches, parses, and stores SEC filing data with complete segment capture
"""

import requests
import json
import pandas as pd
from bs4 import BeautifulSoup
import pdfplumber
import os
import sys
import argparse
import logging
from datetime import datetime
from google.cloud import storage, bigquery
from google.cloud.exceptions import GoogleCloudError
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sec_pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
HEADERS = {'User-Agent': 'mic.b.cunningham@gmail.com'}
PROJECT_ID = 'sec-ai-466316'
BUCKET_NAME = 'sec-ai-analyst'
DATASET_ID = 'sec_data'

class SECDataPipeline:
    def __init__(self, cik: str, filing_type: str = '10-Q', filing_date: Optional[str] = None):
        self.cik = cik.zfill(10)
        self.filing_type = filing_type
        self.filing_date = filing_date
        self.start_time = datetime.now()
        
        # Initialize GCP clients
        try:
            self.storage_client = storage.Client(project=PROJECT_ID)
            self.bq_client = bigquery.Client(project=PROJECT_ID)
            logger.info(f"Initialized GCP clients for project: {PROJECT_ID}")
        except Exception as e:
            logger.error(f"Failed to initialize GCP clients: {e}")
            self.storage_client = None
            self.bq_client = None
    
    def update_filing_status(self, status: str, error_message: str = None):
        """Update filing processing status in BigQuery"""
        if not self.bq_client:
            return
            
        try:
            table_id = f"{PROJECT_ID}.{DATASET_ID}.filing_status"
            
            row = {
                'cik': self.cik,
                'filing_date': self.filing_date or datetime.now().strftime('%Y-%m-%d'),
                'filing_type': self.filing_type,
                'fetch_status': status,
                'error_message': error_message,
                'processing_time_seconds': (datetime.now() - self.start_time).total_seconds(),
                'updated_at': datetime.now().isoformat()
            }
            
            errors = self.bq_client.insert_rows_json(table_id, [row])
            if errors:
                logger.error(f"Failed to update filing status: {errors}")
        except Exception as e:
            logger.error(f"Error updating filing status: {e}")
    
    def fetch_sec_facts(self) -> Optional[Dict]:
        """Fetch Company Facts API data"""
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik}.json"
        
        try:
            logger.info(f"Fetching SEC facts for CIK {self.cik}")
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Save raw data
            with open(f'raw_sec_facts_{self.cik}.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            logger.info(f"Successfully fetched SEC facts for {data.get('entityName', 'Unknown')}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch SEC facts: {e}")
            self.update_filing_status('failed', str(e))
            return None
    
    def fetch_xbrl_instance(self, accession_number: str) -> Optional[str]:
        """Fetch XBRL instance file for complete segment data"""
        try:
            # Get filing index
            accession_clean = accession_number.replace('-', '')
            index_url = f"https://www.sec.gov/Archives/edgar/data/{self.cik.lstrip('0')}/{accession_clean}/index.json"
            
            response = requests.get(index_url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            filing_index = response.json()
            
            # Find instance file
            instance_file = None
            for item in filing_index['directory']['item']:
                if item['name'].endswith('_htm.xml') and 'instance' in item['name'].lower():
                    instance_file = item['name']
                    break
            
            if not instance_file:
                logger.warning("No XBRL instance file found")
                return None
            
            # Download instance file
            instance_url = f"https://www.sec.gov/Archives/edgar/data/{self.cik.lstrip('0')}/{accession_clean}/{instance_file}"
            response = requests.get(instance_url, headers=HEADERS, timeout=60)
            response.raise_for_status()
            
            instance_path = f"xbrl_instance_{self.cik}_{accession_clean}.xml"
            with open(instance_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            logger.info(f"Downloaded XBRL instance: {instance_file}")
            return instance_path
            
        except Exception as e:
            logger.error(f"Failed to fetch XBRL instance: {e}")
            return None
    
    def parse_xbrl_instance(self, instance_path: str) -> Dict:
        """Parse XBRL instance file to extract all facts with segments"""
        try:
            tree = ET.parse(instance_path)
            root = tree.getroot()
            
            # Define namespaces
            namespaces = {
                'xbrli': 'http://www.xbrl.org/2003/instance',
                'us-gaap': root.tag.split('}')[0].strip('{') if 'us-gaap' in root.tag else 'http://fasb.org/us-gaap/2024'
            }
            
            # Update namespaces from root
            for key, value in root.attrib.items():
                if key.startswith('xmlns:'):
                    prefix = key.split(':')[1]
                    namespaces[prefix] = value
            
            facts = []
            segments = {}
            
            # Parse contexts for segments
            contexts = {}
            for context in root.findall('.//xbrli:context', namespaces):
                context_id = context.get('id')
                context_data = {'id': context_id, 'segments': []}
                
                # Check for segments
                for segment in context.findall('.//xbrli:segment//*', namespaces):
                    dimension = segment.tag.split('}')[-1] if '}' in segment.tag else segment.tag
                    member = segment.text or segment.get('value', '')
                    
                    if dimension and member:
                        context_data['segments'].append({
                            'dimension': dimension,
                            'member': member
                        })
                
                contexts[context_id] = context_data
            
            # Parse all facts
            fact_count = 0
            segment_fact_count = 0
            
            for elem in root.iter():
                if '}' in elem.tag and elem.text and elem.text.strip():
                    concept = elem.tag.split('}')[-1]
                    context_ref = elem.get('contextRef')
                    
                    if context_ref and context_ref in contexts:
                        fact = {
                            'concept': concept,
                            'value': elem.text.strip(),
                            'context_id': context_ref,
                            'unit': elem.get('unitRef', 'pure'),
                            'decimals': elem.get('decimals', '0')
                        }
                        
                        # Add segment info if present
                        if contexts[context_ref]['segments']:
                            fact['segments'] = contexts[context_ref]['segments']
                            segment_fact_count += 1
                            
                            # Organize by segment dimension
                            for seg in contexts[context_ref]['segments']:
                                dim = seg['dimension']
                                mem = seg['member']
                                
                                if dim not in segments:
                                    segments[dim] = {}
                                if mem not in segments[dim]:
                                    segments[dim][mem] = []
                                
                                segments[dim][mem].append({
                                    'concept': concept,
                                    'value': elem.text.strip(),
                                    'context': context_ref
                                })
                        
                        facts.append(fact)
                        fact_count += 1
            
            logger.info(f"Parsed XBRL instance: {fact_count} total facts, {segment_fact_count} with segments")
            logger.info(f"Found {len(segments)} segment dimensions")
            
            return {
                'facts': facts,
                'segments': segments,
                'contexts': contexts,
                'stats': {
                    'total_facts': fact_count,
                    'segmented_facts': segment_fact_count,
                    'segment_dimensions': len(segments)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to parse XBRL instance: {e}")
            return {'facts': [], 'segments': {}, 'contexts': {}, 'stats': {}}
    
    def insert_to_bigquery(self, data: Dict) -> Tuple[bool, str]:
        """Insert parsed data into BigQuery with proper error handling"""
        if not self.bq_client:
            return False, "BigQuery client not initialized"
        
        try:
            errors_list = []
            
            # Insert facts
            facts_table = f"{PROJECT_ID}.{DATASET_ID}.facts"
            facts_rows = []
            
            for fact in data.get('facts', []):
                row = {
                    'cik': self.cik,
                    'entity_name': data.get('metadata', {}).get('entityName', ''),
                    'filing_date': self.filing_date or datetime.now().strftime('%Y-%m-%d'),
                    'concept': fact['concept'],
                    'value': float(fact['value']) if fact['value'].replace('.', '').replace('-', '').isdigit() else 0,
                    'unit': fact.get('unit', 'USD'),
                    'context_id': fact.get('context_id', ''),
                    'source': 'xbrl_instance'
                }
                facts_rows.append(row)
            
            if facts_rows:
                errors = self.bq_client.insert_rows_json(facts_table, facts_rows)
                if errors:
                    errors_list.extend(errors)
                    logger.error(f"Facts insertion errors: {errors}")
                else:
                    logger.info(f"Inserted {len(facts_rows)} facts to BigQuery")
            
            # Insert segments (normalized)
            segments_table = f"{PROJECT_ID}.{DATASET_ID}.segments"
            segment_rows = []
            
            for dim_axis, members in data.get('segments', {}).items():
                for member_name, member_facts in members.items():
                    for mf in member_facts:
                        row = {
                            'cik': self.cik,
                            'filing_date': self.filing_date or datetime.now().strftime('%Y-%m-%d'),
                            'dimension_axis': dim_axis,
                            'dimension_member': member_name,
                            'concept': mf['concept'],
                            'value': float(mf['value']) if mf['value'].replace('.', '').replace('-', '').isdigit() else 0,
                            'unit': 'USD',
                            'context_id': mf.get('context', ''),
                            'source': 'xbrl_instance'
                        }
                        segment_rows.append(row)
            
            if segment_rows:
                # Insert in batches to avoid size limits
                batch_size = 500
                for i in range(0, len(segment_rows), batch_size):
                    batch = segment_rows[i:i + batch_size]
                    errors = self.bq_client.insert_rows_json(segments_table, batch)
                    if errors:
                        errors_list.extend(errors)
                        logger.error(f"Segment batch {i//batch_size + 1} errors: {errors}")
                    else:
                        logger.info(f"Inserted segment batch {i//batch_size + 1} ({len(batch)} rows)")
            
            # Update filing status
            self.update_filing_status(
                'completed' if not errors_list else 'completed_with_errors',
                str(errors_list) if errors_list else None
            )
            
            return len(errors_list) == 0, str(errors_list) if errors_list else "Success"
            
        except Exception as e:
            logger.error(f"BigQuery insertion failed: {e}")
            self.update_filing_status('failed', str(e))
            return False, str(e)
    
    def upload_to_gcs(self, file_path: str) -> bool:
        """Upload file to Google Cloud Storage with error handling"""
        if not self.storage_client:
            logger.error("Storage client not initialized")
            return False
            
        try:
            bucket = self.storage_client.bucket(BUCKET_NAME)
            blob_name = f"{self.cik}/{os.path.basename(file_path)}"
            blob = bucket.blob(blob_name)
            
            blob.upload_from_filename(file_path)
            logger.info(f"Uploaded {file_path} to gs://{BUCKET_NAME}/{blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            return False
    
    def run_pipeline(self) -> bool:
        """Run the complete pipeline"""
        try:
            self.update_filing_status('processing')
            
            # Step 1: Fetch SEC facts
            raw_data = self.fetch_sec_facts()
            if not raw_data:
                return False
            
            # Step 2: Get latest filing info
            submissions_url = f"https://data.sec.gov/submissions/CIK{self.cik}.json"
            response = requests.get(submissions_url, headers=HEADERS)
            if response.status_code == 200:
                submissions = response.json()
                recent_filings = submissions.get('filings', {}).get('recent', {})
                
                # Find latest 10-Q
                for i, form in enumerate(recent_filings.get('form', [])):
                    if form == self.filing_type:
                        accession = recent_filings['accessionNumber'][i]
                        self.filing_date = recent_filings['filingDate'][i]
                        break
                
                # Step 3: Fetch and parse XBRL instance
                instance_path = self.fetch_xbrl_instance(accession)
                if instance_path:
                    xbrl_data = self.parse_xbrl_instance(instance_path)
                    
                    # Merge with metadata
                    xbrl_data['metadata'] = {
                        'cik': self.cik,
                        'entityName': raw_data.get('entityName', ''),
                        'filing_date': self.filing_date,
                        'accession_number': accession
                    }
                    
                    # Step 4: Upload to GCS
                    self.upload_to_gcs(instance_path)
                    
                    # Step 5: Insert to BigQuery
                    success, message = self.insert_to_bigquery(xbrl_data)
                    
                    if success:
                        logger.info("Pipeline completed successfully")
                        return True
                    else:
                        logger.error(f"Pipeline completed with errors: {message}")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.update_filing_status('failed', str(e))
            return False

def main():
    parser = argparse.ArgumentParser(description='Fetch and process SEC filing data')
    parser.add_argument('--cik', required=True, help='Company CIK number')
    parser.add_argument('--filing-type', default='10-Q', help='Filing type (10-K, 10-Q, 8-K)')
    parser.add_argument('--date', help='Specific filing date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Run pipeline
    pipeline = SECDataPipeline(args.cik, args.filing_type, args.date)
    success = pipeline.run_pipeline()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()