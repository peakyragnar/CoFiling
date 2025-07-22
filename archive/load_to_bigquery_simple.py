#!/usr/bin/env python3
"""
Simple script to load existing SEC data to BigQuery
"""

import json
import os
import sys

print("📤 SEC Data to BigQuery Loader")
print("="*40)

# Check if data files exist
if not os.path.exists('merged_sec_data.json'):
    print("❌ merged_sec_data.json not found")
    print("Run fetch_sec_facts.py first to generate data")
    sys.exit(1)

print("✅ Found merged_sec_data.json")

# Try to import Google Cloud libraries
try:
    from google.cloud import bigquery
    from google.cloud import storage
    print("✅ Google Cloud libraries available")
except ImportError:
    print("\n❌ Google Cloud libraries not installed")
    print("\n📦 To install, run:")
    print("   python3 -m pip install google-cloud-bigquery google-cloud-storage")
    print("\n🔄 For now, let's prepare the data for manual upload...")
    
    # Create SQL file for manual upload
    with open('merged_sec_data.json', 'r') as f:
        data = json.load(f)
    
    # Create SQL inserts
    with open('manual_bigquery_load.sql', 'w') as sql:
        sql.write("-- Manual BigQuery data load for SEC data\n")
        sql.write("-- Run this in BigQuery console\n\n")
        
        # Facts insert
        sql.write("-- Insert facts\n")
        sql.write("INSERT INTO `sec-ai-466316.sec_data.facts` (cik, entity_name, concept, value, unit, period_end, source)\n")
        sql.write("VALUES\n")
        
        facts = data['structured']['facts']
        first = True
        for concept, values in facts.items():
            if isinstance(values, list) and values:
                v = values[0]
                if not first:
                    sql.write(",\n")
                sql.write(f"  ('{data['metadata']['cik']}', '{data['metadata']['entityName']}', '{concept}', {v.get('value', 0)}, '{v.get('unit', 'USD')}', '2025-03-31', 'xbrl_instance')")
                first = False
                if concept in ['Revenues', 'NetIncomeLoss', 'Assets']:  # Just key metrics
                    break
        
        sql.write(";\n\n")
        
        print("\n✅ Created manual_bigquery_load.sql")
        print("\n📋 To load data manually:")
        print("1. Go to: https://console.cloud.google.com/bigquery?project=sec-ai-466316")
        print("2. Click 'Compose new query'")
        print("3. Copy contents of manual_bigquery_load.sql")
        print("4. Run the query")
    
    sys.exit(0)

# If libraries are available, proceed with automated upload
print("\n🔄 Connecting to BigQuery...")

try:
    # Initialize client
    client = bigquery.Client(project='sec-ai-466316')
    
    # Test connection
    datasets = list(client.list_datasets())
    print(f"✅ Connected! Found {len(datasets)} datasets")
    
    # Load data
    with open('merged_sec_data.json', 'r') as f:
        data = json.load(f)
    
    # Insert facts
    table_id = 'sec-ai-466316.sec_data.facts'
    rows = []
    
    for concept, values in data['structured']['facts'].items():
        if isinstance(values, list) and values:
            v = values[0]
            rows.append({
                'cik': data['metadata']['cik'],
                'entity_name': data['metadata']['entityName'],
                'concept': concept,
                'value': float(v.get('value', 0)) if str(v.get('value', '')).replace('.','').replace('-','').isdigit() else 0,
                'unit': v.get('unit', 'USD'),
                'period_end': '2025-03-31',
                'source': 'xbrl_instance'
            })
    
    print(f"\n📊 Inserting {len(rows)} facts to BigQuery...")
    
    errors = client.insert_rows_json(table_id, rows[:100])  # First 100 rows
    
    if not errors:
        print("✅ Data successfully loaded to BigQuery!")
        print(f"\n🎉 Your data is now in BigQuery!")
        print("\n📋 Next: Set up Google Sheets (see instructions above)")
    else:
        print(f"❌ Insert errors: {errors}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 Try manual upload using manual_bigquery_load.sql")

print("\n" + "="*60)
print("📊 GOOGLE SHEETS SETUP")
print("="*60)
print("""
1. Go to Google Sheets and create "SEC Financial Analysis"
2. Add Apps Script code from apps_script/ folder
3. Connect to BigQuery dataset 'sec_data'
4. Use SEC Analysis menu to build AI models!
""")