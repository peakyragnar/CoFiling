"""
Cloud Function: Process SEC Filing
Triggered by GCS upload to parse and extract data from SEC filings
"""

import functions_framework
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from google.cloud import storage, bigquery, pubsub_v1
import os
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
PROJECT_ID = os.environ.get('GCP_PROJECT', 'sec-ai-466316')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'sec-ai-analyst')
DATASET_ID = os.environ.get('DATASET_ID', 'sec_data')
AI_TOPIC = os.environ.get('AI_TOPIC', 'sec-filing-ai-enrichment')

HEADERS = {'User-Agent': os.environ.get('SEC_USER_AGENT', 'mic.b.cunningham@gmail.com')}

@functions_framework.cloud_event
def process_filing(cloud_event):
    """
    Process SEC filing when metadata.json is uploaded to GCS
    """
    
    try:
        # Parse GCS event
        file_info = cloud_event.data
        file_name = file_info['name']
        
        # Only process metadata files
        if not file_name.endswith('metadata.json'):
            logger.info(f"Skipping non-metadata file: {file_name}")
            return {"status": "skipped"}
        
        logger.info(f"Processing filing from: {file_name}")
        
        # Download and parse metadata
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        
        metadata = json.loads(blob.download_as_text())
        
        # Fetch and parse XBRL instance
        xbrl_data = fetch_and_parse_xbrl(metadata)
        
        if xbrl_data:
            # Store structured data
            store_structured_data(metadata, xbrl_data)
            
            # Publish for AI enrichment
            publish_for_ai_enrichment(metadata, xbrl_data)
            
            # Update metadata status
            metadata['status'] = 'processed'
            metadata['processed_at'] = datetime.now().isoformat()
            metadata['stats'] = xbrl_data.get('stats', {})
            
            blob.upload_from_string(
                json.dumps(metadata, indent=2),
                content_type='application/json'
            )
            
            return {"status": "success", "stats": xbrl_data.get('stats', {})}
        else:
            return {"status": "error", "error": "Failed to parse XBRL"}
            
    except Exception as e:
        logger.error(f"Error processing filing: {e}")
        return {"status": "error", "error": str(e)}

def fetch_and_parse_xbrl(metadata: dict) -> dict:
    """Fetch and parse XBRL instance file"""
    
    try:
        # Construct XBRL instance URL
        cik = metadata['cik'].lstrip('0')
        accession = metadata['accession_number'].replace('-', '')
        
        # Get filing index
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.json"
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
            logger.error("No XBRL instance file found")
            return None
        
        # Download instance
        instance_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{instance_file}"
        response = requests.get(instance_url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        
        # Parse XBRL
        return parse_xbrl_content(response.text, metadata)
        
    except Exception as e:
        logger.error(f"Error fetching XBRL: {e}")
        return None

def parse_xbrl_content(xml_content: str, metadata: dict) -> dict:
    """Parse XBRL XML content"""
    
    try:
        root = ET.fromstring(xml_content)
        
        # Extract namespaces
        namespaces = {}
        for key, value in root.attrib.items():
            if key.startswith('xmlns:'):
                prefix = key.split(':')[1]
                namespaces[prefix] = value
        
        # Parse contexts for segments
        contexts = {}
        for context in root.findall('.//{http://www.xbrl.org/2003/instance}context'):
            context_id = context.get('id')
            segments = []
            
            # Look for segment information
            for segment in context.findall('.//{http://www.xbrl.org/2003/instance}segment//*'):
                dimension = segment.tag.split('}')[-1] if '}' in segment.tag else segment.tag
                member = segment.text or segment.get('value', '')
                
                if dimension and member:
                    segments.append({
                        'dimension': dimension,
                        'member': member
                    })
            
            contexts[context_id] = {
                'id': context_id,
                'segments': segments,
                'instant': None,
                'start_date': None,
                'end_date': None
            }
            
            # Extract period info
            for instant in context.findall('.//{http://www.xbrl.org/2003/instance}instant'):
                contexts[context_id]['instant'] = instant.text
            
            for period in context.findall('.//{http://www.xbrl.org/2003/instance}period'):
                start = period.find('{http://www.xbrl.org/2003/instance}startDate')
                end = period.find('{http://www.xbrl.org/2003/instance}endDate')
                if start is not None:
                    contexts[context_id]['start_date'] = start.text
                if end is not None:
                    contexts[context_id]['end_date'] = end.text
        
        # Parse facts
        facts = []
        segments_by_dimension = {}
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
                        'unit': elem.get('unitRef', 'USD'),
                        'decimals': elem.get('decimals'),
                        'period_end': contexts[context_ref]['end_date'] or contexts[context_ref]['instant']
                    }
                    
                    # Handle segments
                    if contexts[context_ref]['segments']:
                        fact['segments'] = contexts[context_ref]['segments']
                        segment_fact_count += 1
                        
                        # Organize by dimension
                        for seg in contexts[context_ref]['segments']:
                            dim = seg['dimension']
                            mem = seg['member']
                            
                            if dim not in segments_by_dimension:
                                segments_by_dimension[dim] = {}
                            if mem not in segments_by_dimension[dim]:
                                segments_by_dimension[dim][mem] = []
                            
                            segments_by_dimension[dim][mem].append({
                                'concept': concept,
                                'value': fact['value'],
                                'period_end': fact['period_end'],
                                'context': context_ref
                            })
                    
                    facts.append(fact)
                    fact_count += 1
        
        logger.info(f"Parsed {fact_count} facts, {segment_fact_count} with segments")
        
        return {
            'facts': facts,
            'segments': segments_by_dimension,
            'contexts': contexts,
            'stats': {
                'total_facts': fact_count,
                'segmented_facts': segment_fact_count,
                'segment_dimensions': len(segments_by_dimension),
                'unique_concepts': len(set(f['concept'] for f in facts))
            }
        }
        
    except Exception as e:
        logger.error(f"Error parsing XBRL: {e}")
        return None

def store_structured_data(metadata: dict, xbrl_data: dict):
    """Store parsed data in BigQuery"""
    
    try:
        client = bigquery.Client(project=PROJECT_ID)
        
        # Prepare facts for insertion
        facts_rows = []
        for fact in xbrl_data['facts']:
            row = {
                'cik': metadata['cik'],
                'entity_name': metadata['entity_name'],
                'filing_date': metadata['filing_date'],
                'period_end': fact['period_end'],
                'concept': fact['concept'],
                'value': float(fact['value']) if fact['value'].replace('.', '').replace('-', '').isdigit() else None,
                'unit': fact['unit'],
                'context_id': fact['context_id'],
                'source': 'xbrl_instance',
                'created_at': datetime.now().isoformat()
            }
            
            # Add segment info if present
            if 'segments' in fact and fact['segments']:
                # For facts table, we'll store the first segment dimension/member
                seg = fact['segments'][0]
                row['segment_dimension'] = seg['dimension']
                row['segment_member'] = seg['member']
            
            facts_rows.append(row)
        
        # Insert facts
        if facts_rows:
            table_id = f"{PROJECT_ID}.{DATASET_ID}.facts"
            errors = client.insert_rows_json(table_id, facts_rows)
            
            if errors:
                logger.error(f"Failed to insert facts: {errors}")
            else:
                logger.info(f"Inserted {len(facts_rows)} facts")
        
        # Insert segments (normalized)
        segment_rows = []
        for dimension, members in xbrl_data['segments'].items():
            for member, member_facts in members.items():
                for mf in member_facts:
                    row = {
                        'cik': metadata['cik'],
                        'filing_date': metadata['filing_date'],
                        'dimension_axis': dimension,
                        'dimension_member': member,
                        'concept': mf['concept'],
                        'period_end': mf['period_end'],
                        'value': float(mf['value']) if mf['value'].replace('.', '').replace('-', '').isdigit() else None,
                        'unit': 'USD',
                        'context_id': mf['context'],
                        'source': 'xbrl_instance',
                        'created_at': datetime.now().isoformat()
                    }
                    segment_rows.append(row)
        
        # Insert segments in batches
        if segment_rows:
            table_id = f"{PROJECT_ID}.{DATASET_ID}.segments"
            batch_size = 500
            
            for i in range(0, len(segment_rows), batch_size):
                batch = segment_rows[i:i + batch_size]
                errors = client.insert_rows_json(table_id, batch)
                
                if errors:
                    logger.error(f"Failed to insert segment batch: {errors}")
                else:
                    logger.info(f"Inserted segment batch {i//batch_size + 1}")
        
    except Exception as e:
        logger.error(f"Error storing data: {e}")

def publish_for_ai_enrichment(metadata: dict, xbrl_data: dict):
    """Publish data for AI enrichment"""
    
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, AI_TOPIC)
        
        # Create message with key data for AI processing
        message = {
            'metadata': metadata,
            'stats': xbrl_data['stats'],
            'sample_facts': xbrl_data['facts'][:10],  # Send sample for AI
            'segment_dimensions': list(xbrl_data['segments'].keys()),
            'timestamp': datetime.now().isoformat()
        }
        
        future = publisher.publish(
            topic_path,
            json.dumps(message).encode('utf-8')
        )
        
        future.result()
        logger.info(f"Published for AI enrichment: {metadata['accession_number']}")
        
    except Exception as e:
        logger.error(f"Error publishing for AI: {e}")