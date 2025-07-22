#!/usr/bin/env python3
"""
Verify GCP Storage - Check if SEC data is correctly stored in GCS and BigQuery
"""

import json
import sys
from datetime import datetime
from google.cloud import storage
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# GCP Configuration
PROJECT_ID = 'sec-ai-466316'
BUCKET_NAME = 'sec-ai-analyst'
DATASET_ID = 'sec_data'

def verify_gcs_upload(file_name='merged_sec_data.json'):
    """Verify file exists in GCS bucket and compare with local file"""
    print(f"\n=== GCS Verification ===")
    print(f"Project: {PROJECT_ID}")
    print(f"Bucket: {BUCKET_NAME}")
    print(f"File: {file_name}")
    
    try:
        # Initialize client
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        
        # Check if blob exists
        if blob.exists():
            print(f"✓ File exists in GCS")
            
            # Get blob metadata
            blob.reload()
            print(f"  - Size: {blob.size:,} bytes")
            print(f"  - Updated: {blob.updated}")
            print(f"  - Content Type: {blob.content_type}")
            
            # Compare with local file
            try:
                import os
                local_size = os.path.getsize(file_name)
                print(f"  - Local file size: {local_size:,} bytes")
                if local_size == blob.size:
                    print(f"  ✓ File sizes match")
                else:
                    print(f"  ✗ File sizes don't match! Local: {local_size}, GCS: {blob.size}")
            except FileNotFoundError:
                print(f"  - Local file not found for comparison")
            
            return True
        else:
            print(f"✗ File NOT found in GCS bucket")
            return False
            
    except Exception as e:
        print(f"✗ Error accessing GCS: {e}")
        return False

def verify_bigquery_tables():
    """Verify BigQuery tables exist and contain data"""
    print(f"\n=== BigQuery Verification ===")
    print(f"Project: {PROJECT_ID}")
    print(f"Dataset: {DATASET_ID}")
    
    try:
        client = bigquery.Client(project=PROJECT_ID)
        dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
        
        # Check if dataset exists
        try:
            dataset = client.get_dataset(dataset_ref)
            print(f"✓ Dataset '{DATASET_ID}' exists")
        except NotFound:
            print(f"✗ Dataset '{DATASET_ID}' NOT found")
            return False
        
        # Check tables
        tables_to_check = ['texts', 'facts']
        results = {}
        
        for table_name in tables_to_check:
            table_ref = f"{dataset_ref}.{table_name}"
            print(f"\nTable: {table_name}")
            
            try:
                table = client.get_table(table_ref)
                print(f"  ✓ Table exists")
                print(f"  - Total rows: {table.num_rows:,}")
                print(f"  - Size: {table.num_bytes:,} bytes")
                
                # Get recent records
                query = f"""
                SELECT * FROM `{table_ref}` 
                ORDER BY created_at DESC 
                LIMIT 5
                """
                
                try:
                    recent_rows = list(client.query(query))
                    if recent_rows:
                        print(f"  - Recent records: {len(recent_rows)}")
                        
                        # For facts table, check for segment data
                        if table_name == 'facts' and recent_rows:
                            segment_query = f"""
                            SELECT COUNT(*) as segment_count
                            FROM `{table_ref}`
                            WHERE segment_dimension IS NOT NULL
                            """
                            segment_result = list(client.query(segment_query))
                            if segment_result:
                                segment_count = segment_result[0]['segment_count']
                                print(f"  - Facts with segments: {segment_count}")
                    else:
                        print(f"  - No records found")
                        
                except Exception as e:
                    print(f"  - Error querying table: {e}")
                
                results[table_name] = True
                
            except NotFound:
                print(f"  ✗ Table NOT found")
                results[table_name] = False
            except Exception as e:
                print(f"  ✗ Error accessing table: {e}")
                results[table_name] = False
        
        return all(results.values())
        
    except Exception as e:
        print(f"✗ Error accessing BigQuery: {e}")
        return False

def verify_tesla_data():
    """Verify Tesla-specific data was uploaded correctly"""
    print(f"\n=== Tesla Data Verification ===")
    
    try:
        client = bigquery.Client(project=PROJECT_ID)
        
        # Check for Tesla CIK in texts table
        texts_query = f"""
        SELECT cik, entity_name, filing_date, created_at
        FROM `{PROJECT_ID}.{DATASET_ID}.texts`
        WHERE cik = '0001318605'
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        texts_results = list(client.query(texts_query))
        if texts_results:
            print(f"✓ Found Tesla filing in texts table")
            for row in texts_results:
                print(f"  - Entity: {row.entity_name}")
                print(f"  - Filing Date: {row.filing_date}")
                print(f"  - Uploaded: {row.created_at}")
        else:
            print(f"✗ No Tesla data found in texts table")
        
        # Check for Tesla facts with segments
        facts_query = f"""
        SELECT 
            COUNT(*) as total_facts,
            COUNT(DISTINCT segment_dimension) as unique_segments,
            COUNT(CASE WHEN segment_dimension IS NOT NULL THEN 1 END) as segmented_facts
        FROM `{PROJECT_ID}.{DATASET_ID}.facts`
        WHERE cik = '0001318605'
        """
        
        facts_results = list(client.query(facts_query))
        if facts_results and facts_results[0]['total_facts'] > 0:
            print(f"\n✓ Found Tesla facts in facts table")
            result = facts_results[0]
            print(f"  - Total facts: {result.total_facts}")
            print(f"  - Segmented facts: {result.segmented_facts}")
            print(f"  - Unique segment dimensions: {result.unique_segments}")
            
            # Sample some segment dimensions
            segment_sample_query = f"""
            SELECT DISTINCT segment_dimension
            FROM `{PROJECT_ID}.{DATASET_ID}.facts`
            WHERE cik = '0001318605' AND segment_dimension IS NOT NULL
            LIMIT 10
            """
            
            segment_samples = list(client.query(segment_sample_query))
            if segment_samples:
                print(f"\n  Sample segment dimensions:")
                for row in segment_samples:
                    print(f"    - {row.segment_dimension}")
                    
            return True
        else:
            print(f"✗ No Tesla facts found in facts table")
            return False
            
    except Exception as e:
        print(f"✗ Error verifying Tesla data: {e}")
        return False

def main():
    """Run all verifications"""
    print("SEC Data GCP Storage Verification")
    print("=" * 50)
    
    # Track results
    results = {
        'GCS Upload': verify_gcs_upload(),
        'BigQuery Tables': verify_bigquery_tables(),
        'Tesla Data': verify_tesla_data()
    }
    
    # Summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    for check, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{check}: {status}")
    
    if all(results.values()):
        print("\n✓ ALL CHECKS PASSED - Data is correctly stored in GCP")
        return 0
    else:
        print("\n✗ SOME CHECKS FAILED - Please review the issues above")
        return 1

if __name__ == "__main__":
    sys.exit(main())