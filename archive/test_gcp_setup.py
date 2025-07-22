#!/usr/bin/env python3
"""
Test Google Cloud setup and run initial data load
"""

import subprocess
import sys
import os
import json

def check_gcloud_auth():
    """Check if gcloud is authenticated"""
    print("🔐 Checking Google Cloud authentication...")
    
    result = subprocess.run(['gcloud', 'auth', 'list'], capture_output=True, text=True)
    
    if "No credentialed accounts" in result.stdout:
        print("❌ Not authenticated with Google Cloud")
        print("\nPlease run:")
        print("  gcloud auth login")
        print("  gcloud auth application-default login")
        return False
    else:
        print("✅ Authenticated with Google Cloud")
        print(result.stdout)
        return True

def test_bigquery_access():
    """Test BigQuery access"""
    print("\n📊 Testing BigQuery access...")
    
    try:
        # Test listing datasets
        result = subprocess.run(
            ['bq', 'ls', '--project_id=sec-ai-466316'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ BigQuery access confirmed")
            if 'sec_data' in result.stdout:
                print("  ✓ Dataset 'sec_data' exists")
            else:
                print("  ℹ️ Dataset 'sec_data' not found - will create")
            return True
        else:
            print("❌ BigQuery access failed")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error testing BigQuery: {e}")
        return False

def test_gcs_access():
    """Test Google Cloud Storage access"""
    print("\n☁️ Testing Cloud Storage access...")
    
    try:
        result = subprocess.run(
            ['gsutil', 'ls', 'gs://sec-ai-analyst/'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Cloud Storage bucket exists")
            return True
        else:
            print("ℹ️ Bucket doesn't exist - will create")
            return True  # Not an error, we'll create it
    except Exception as e:
        print(f"❌ Error testing Cloud Storage: {e}")
        return False

def run_setup_script():
    """Run the setup script"""
    print("\n🚀 Running setup script...")
    
    if os.path.exists('setup_bigquery.sh'):
        result = subprocess.run(['bash', 'setup_bigquery.sh'], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Setup completed successfully!")
            print(result.stdout)
            return True
        else:
            print("❌ Setup failed:")
            print(result.stderr)
            return False
    else:
        print("❌ setup_bigquery.sh not found")
        return False

def load_initial_data():
    """Load Tesla data into BigQuery"""
    print("\n📤 Loading initial data to BigQuery...")
    
    if os.path.exists('fetch_sec_facts_v2.py'):
        # Install dependencies first
        print("Installing Python dependencies...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 
                       'requests', 'google-cloud-storage', 'google-cloud-bigquery'],
                      capture_output=True)
        
        # Run the enhanced fetcher
        result = subprocess.run(
            [sys.executable, 'fetch_sec_facts_v2.py', '--cik', '0001318605'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Data loaded successfully!")
            return True
        else:
            print("❌ Data load failed:")
            print(result.stderr)
            # Try the original script as fallback
            print("\n🔄 Trying original script...")
            result = subprocess.run([sys.executable, 'fetch_sec_facts.py'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
    
    return False

def show_next_steps():
    """Show next steps for Google Sheets setup"""
    print("\n" + "="*60)
    print("📋 NEXT STEPS: Set up Google Sheets with AI")
    print("="*60)
    
    print("""
1. CREATE GOOGLE SHEET:
   - Go to: https://sheets.google.com
   - Create new spreadsheet
   - Name it: "SEC Financial Analysis"

2. ADD APPS SCRIPT (this enables AI features):
   - In the Sheet: Extensions → Apps Script
   - Delete all default code
   - Create 3 files and copy code from:
     • Code.gs → apps_script/Code.gs
     • GeminiIntegration.gs → apps_script/GeminiIntegration.gs
     • CompanyConfig.html → apps_script/CompanyConfig.html
   - Save all files (Ctrl+S or Cmd+S)

3. ENABLE BIGQUERY API:
   - Still in Apps Script
   - Click "Services" (+ icon on left)
   - Find and add "BigQuery API"
   - Click "Add"

4. CONNECT TO YOUR DATA:
   - Close Apps Script and return to Sheet
   - Refresh the page (F5)
   - You should see "SEC Analysis" menu
   - Data → Data connectors → Connect to BigQuery
   - Choose project: sec-ai-466316
   - Choose dataset: sec_data
   - Select tables: company_summary, segment_performance

5. USE AI FEATURES:
   - SEC Analysis → Build Financial Model
   - SEC Analysis → Generate AI Summary
   - Use formulas: =AI("analyze this data", A1:B10)

The system will now:
✓ Automatically fetch SEC data daily
✓ Use AI to analyze and categorize
✓ Update your models automatically
✓ Generate insights with Gemini
""")

def main():
    print("🚀 Google Cloud SEC Pipeline Setup")
    print("="*40)
    
    # Check authentication
    if not check_gcloud_auth():
        print("\n⚠️ Please authenticate first, then run this script again")
        return
    
    # Test access
    bq_ok = test_bigquery_access()
    gcs_ok = test_gcs_access()
    
    if not (bq_ok and gcs_ok):
        print("\n⚠️ Some services aren't accessible. Running setup...")
    
    # Run setup
    if input("\n▶️ Run setup script? (y/n): ").lower() == 'y':
        if run_setup_script():
            # Load initial data
            if input("\n▶️ Load Tesla data to BigQuery? (y/n): ").lower() == 'y':
                load_initial_data()
    
    # Show next steps
    show_next_steps()

if __name__ == "__main__":
    main()