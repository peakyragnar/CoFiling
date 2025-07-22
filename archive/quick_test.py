#!/usr/bin/env python3
"""
Quick test to run the pipeline locally and verify data before setting up Google Sheets
"""

import json
import os
import subprocess
import sys

def check_dependencies():
    """Check if required packages are installed"""
    required = ['requests', 'pandas', 'beautifulsoup4', 'pdfplumber']
    missing = []
    
    for package in required:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"\nInstall with: pip3 install {' '.join(missing)}")
        return False
    
    print("✅ All required packages installed")
    return True

def run_basic_test():
    """Run the original fetch_sec_facts.py to test basic functionality"""
    print("\n📊 Running SEC data fetch for Tesla...")
    
    try:
        # Run the original script that works without Google Cloud
        result = subprocess.run(
            ['python3', 'fetch_sec_facts.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Data fetched successfully!")
            
            # Check output files
            files_to_check = [
                'raw_sec_facts.json',
                'formatted_sec_data.json',
                'merged_sec_data.json'
            ]
            
            for file in files_to_check:
                if os.path.exists(file):
                    size = os.path.getsize(file) / 1024 / 1024  # MB
                    print(f"  ✓ {file}: {size:.1f} MB")
                    
                    # Show sample data from merged file
                    if file == 'merged_sec_data.json':
                        with open(file, 'r') as f:
                            data = json.load(f)
                        
                        print(f"\n📈 Company: {data['metadata']['entityName']}")
                        print(f"📅 CIK: {data['metadata']['cik']}")
                        
                        # Show segment dimensions
                        if 'structured' in data and 'segments' in data['structured']:
                            segments = data['structured']['segments']
                            print(f"\n🔍 Segment Dimensions Found: {len(segments)}")
                            for i, (dim, members) in enumerate(list(segments.items())[:5]):
                                print(f"  {i+1}. {dim}: {len(members)} members")
                        
                        # Show sample facts
                        if 'structured' in data and 'facts' in data['structured']:
                            facts = data['structured']['facts']
                            print(f"\n💰 Financial Facts Found: {len(facts)} concepts")
                            
                            # Show revenue if available
                            if 'Revenues' in facts and facts['Revenues']:
                                latest_revenue = facts['Revenues'][0]
                                print(f"  Latest Revenue: ${latest_revenue['value']:,.0f}")
                else:
                    print(f"  ❌ {file} not found")
            
            return True
        else:
            print(f"❌ Error running script: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def show_next_steps():
    """Show instructions for Google Sheets setup"""
    print("\n" + "="*60)
    print("📋 NEXT STEPS: Set up Google Sheets")
    print("="*60)
    
    print("""
1. INSTALL DEPENDENCIES (if not already done):
   pip3 install requests pandas beautifulsoup4 pdfplumber

2. CREATE GOOGLE SHEET:
   a. Go to: https://sheets.google.com
   b. Create new spreadsheet
   c. Name it: "SEC Financial Analysis"

3. ADD APPS SCRIPT:
   a. In the Sheet: Extensions → Apps Script
   b. Delete default code
   c. Copy contents from:
      - apps_script/Code.gs
      - apps_script/GeminiIntegration.gs
   d. File → New → HTML file → name it "CompanyConfig"
   e. Copy contents from apps_script/CompanyConfig.html
   f. Save all files (Ctrl+S)

4. ENABLE APIS:
   a. In Apps Script: Services → Add Service
   b. Add "BigQuery API"
   c. Click "Add"

5. CLOSE AND REFRESH:
   a. Close Apps Script tab
   b. Refresh your Google Sheet
   c. You should see: SEC Analysis menu

6. USE WITHOUT BIGQUERY (for testing):
   Since BigQuery isn't set up yet, you can:
   a. Copy data from merged_sec_data.json manually
   b. Or wait to set up full BigQuery integration

Would you like to see the data in a simple format first?
""")

def create_simple_csv():
    """Create a simple CSV that can be imported to Google Sheets"""
    print("\n📊 Creating simple CSV for Google Sheets...")
    
    try:
        import pandas as pd
        
        # Load merged data
        with open('merged_sec_data.json', 'r') as f:
            data = json.load(f)
        
        # Extract key facts
        facts_data = []
        facts = data['structured']['facts']
        
        for concept, values in facts.items():
            if values and isinstance(values, list):
                for v in values[:1]:  # Just latest value
                    facts_data.append({
                        'Concept': concept,
                        'Value': v.get('value', 0),
                        'Period': v.get('period', ''),
                        'Unit': v.get('unit', 'USD')
                    })
        
        # Create DataFrame and save
        df = pd.DataFrame(facts_data)
        df.to_csv('tesla_financials.csv', index=False)
        print(f"✅ Created tesla_financials.csv with {len(df)} rows")
        print("\n🔄 You can now:")
        print("   1. Open Google Sheets")
        print("   2. File → Import → Upload tesla_financials.csv")
        print("   3. See the financial data immediately!")
        
        # Show preview
        print("\nPreview of data:")
        print(df.head(10).to_string())
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating CSV: {e}")
        return False

def main():
    print("🚀 SEC Data Pipeline - Quick Test")
    print("="*60)
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Run basic test
    if run_basic_test():
        # Create simple CSV
        create_simple_csv()
    
    # Show next steps
    show_next_steps()

if __name__ == "__main__":
    main()