#!/usr/bin/env python3
"""
Simple GCP Storage Verification - Check configuration and provide manual steps
"""

import json
import os

def check_local_files():
    """Check if local files exist that should be uploaded"""
    print("=== Local File Check ===")
    
    files_to_check = ['merged_sec_data.json', 'formatted_sec_data.json', 'raw_sec_facts.json']
    found_files = {}
    
    for file_name in files_to_check:
        if os.path.exists(file_name):
            size = os.path.getsize(file_name)
            found_files[file_name] = size
            print(f"✓ {file_name}: {size:,} bytes")
            
            # Check if it has segment data
            if file_name == 'merged_sec_data.json':
                try:
                    with open(file_name, 'r') as f:
                        data = json.load(f)
                    
                    # Check for segments
                    if 'structured' in data and 'segments' in data['structured']:
                        segments = data['structured']['segments']
                        segment_count = len(segments)
                        total_segment_facts = sum(
                            len(member_data) 
                            for axis_data in segments.values() 
                            for member_data in axis_data.values()
                        )
                        print(f"  - Segment dimensions: {segment_count}")
                        print(f"  - Total segmented facts: {total_segment_facts}")
                except Exception as e:
                    print(f"  - Error reading file: {e}")
        else:
            print(f"✗ {file_name}: NOT FOUND")
    
    return found_files

def check_gcp_config():
    """Check if GCP configuration is set in fetch_sec_facts.py"""
    print("\n=== GCP Configuration Check ===")
    
    if os.path.exists('fetch_sec_facts.py'):
        with open('fetch_sec_facts.py', 'r') as f:
            content = f.read()
        
        # Check for GCP configurations
        configs = {
            'Project ID': "project_id = 'sec-ai-466316'",
            'GCS Bucket': "bucket_name='sec-ai-analyst'",
            'BigQuery Dataset': "dataset_id = 'sec_data'",
            'GCS Upload Function': "def upload_to_gcs",
            'BigQuery Insert Function': "def insert_to_bigquery"
        }
        
        for name, pattern in configs.items():
            if pattern in content:
                print(f"✓ {name}: Found")
            else:
                print(f"✗ {name}: NOT Found")
                
        # Check if functions are called
        if "upload_to_gcs('merged_sec_data.json')" in content:
            print(f"✓ GCS upload is called in script")
        else:
            print(f"✗ GCS upload NOT called in script")
            
        if "insert_to_bigquery(merged_data)" in content:
            print(f"✓ BigQuery insert is called in script")
        else:
            print(f"✗ BigQuery insert NOT called in script")
    else:
        print("✗ fetch_sec_facts.py not found")

def provide_manual_steps():
    """Provide manual verification steps"""
    print("\n=== Manual Verification Steps ===")
    print("\n1. **Verify GCS Upload** (in Google Cloud Console):")
    print("   - Go to: https://console.cloud.google.com/storage/browser/sec-ai-analyst")
    print("   - Project: sec-ai-466316")
    print("   - Look for: merged_sec_data.json")
    print("   - Check file size and upload time")
    
    print("\n2. **Verify BigQuery Tables** (in BigQuery Console):")
    print("   - Go to: https://console.cloud.google.com/bigquery")
    print("   - Project: sec-ai-466316")
    print("   - Dataset: sec_data")
    print("   - Check tables: 'texts' and 'facts'")
    print("   - Run this query to check Tesla data:")
    print("""
   SELECT COUNT(*) as total_facts,
          COUNT(DISTINCT segment_dimension) as unique_segments
   FROM `sec-ai-466316.sec_data.facts`
   WHERE cik = '0001318605'
   """)
    
    print("\n3. **Using gcloud CLI** (if authenticated):")
    print("   ```bash")
    print("   # List files in bucket")
    print("   gcloud storage ls gs://sec-ai-analyst/")
    print("   ")
    print("   # Check file details")
    print("   gcloud storage stat gs://sec-ai-analyst/merged_sec_data.json")
    print("   ")
    print("   # Query BigQuery")
    print("   bq query --project_id=sec-ai-466316 'SELECT COUNT(*) FROM sec_data.facts'")
    print("   ```")
    
    print("\n4. **Check Script Output**:")
    print("   When fetch_sec_facts.py runs successfully, you should see:")
    print("   - 'Uploaded merged_sec_data.json to GCS.'")
    print("   - 'Text inserted to BigQuery.'")
    print("   - 'Facts/segments inserted to BigQuery.'")
    print("   - Or error messages if uploads failed")

def main():
    print("GCP Storage Configuration & Manual Verification Guide")
    print("=" * 60)
    
    # Check local files
    local_files = check_local_files()
    
    # Check GCP configuration
    check_gcp_config()
    
    # Provide manual steps
    provide_manual_steps()
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    
    if 'merged_sec_data.json' in local_files:
        print("✓ Your merged data file exists locally")
        print("→ Follow the manual verification steps above to confirm GCP uploads")
    else:
        print("✗ No merged_sec_data.json found")
        print("→ Run fetch_sec_facts.py first to generate the data")
    
    print("\nIf you see errors during upload:")
    print("1. Check your Google Cloud authentication")
    print("2. Verify you have permissions for project 'sec-ai-466316'")
    print("3. Check if the bucket 'sec-ai-analyst' exists")
    print("4. Ensure BigQuery dataset 'sec_data' exists with correct schema")

if __name__ == "__main__":
    main()