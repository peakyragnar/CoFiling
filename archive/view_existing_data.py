#!/usr/bin/env python3
"""
View existing SEC data and create a simple CSV for Google Sheets
"""

import json
import csv

def create_financial_summary():
    """Create a simple financial summary from existing data"""
    
    try:
        # Load the merged data
        print("📊 Loading existing Tesla financial data...")
        with open('merged_sec_data.json', 'r') as f:
            data = json.load(f)
        
        print(f"✅ Company: {data['metadata']['entityName']}")
        print(f"📅 CIK: {data['metadata']['cik']}")
        
        # Create a simple CSV with key financials
        with open('tesla_financial_summary.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write headers
            writer.writerow(['Financial Metric', 'Value', 'Unit', 'Period'])
            
            # Extract key facts
            facts = data['structured']['facts']
            key_metrics = [
                'Revenues', 
                'CostOfRevenue',
                'GrossProfit',
                'OperatingIncomeLoss',
                'NetIncomeLoss',
                'Assets',
                'Liabilities',
                'StockholdersEquity',
                'CashAndCashEquivalentsAtCarryingValue',
                'EarningsPerShareBasic'
            ]
            
            rows_written = 0
            for metric in key_metrics:
                if metric in facts and facts[metric]:
                    # Get the most recent value
                    latest = facts[metric][0] if isinstance(facts[metric], list) else facts[metric]
                    if isinstance(latest, dict):
                        value = latest.get('value', 'N/A')
                        period = latest.get('period', '2025-03-31')
                        unit = latest.get('unit', 'USD')
                        
                        # Format large numbers
                        if isinstance(value, (int, float)) and value > 1000000:
                            formatted_value = f"{value/1000000:,.1f}M"
                        else:
                            formatted_value = str(value)
                        
                        writer.writerow([metric, formatted_value, unit, period])
                        rows_written += 1
            
            # Add segment data summary
            writer.writerow([])  # Empty row
            writer.writerow(['Segment Analysis', '', '', ''])
            writer.writerow(['Dimension', 'Members Count', '', ''])
            
            segments = data['structured']['segments']
            for dimension, members in segments.items():
                writer.writerow([dimension, len(members), '', ''])
            
            print(f"\n✅ Created tesla_financial_summary.csv with {rows_written} key metrics")
        
        # Also create a segment breakdown CSV
        with open('tesla_segment_breakdown.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Segment Dimension', 'Member', 'Sample Metric', 'Value'])
            
            # Show first few segments
            segment_rows = 0
            for dimension, members in list(segments.items())[:5]:
                for member, data_list in list(members.items())[:3]:
                    if isinstance(data_list, list) and data_list:
                        sample = data_list[0]
                        if isinstance(sample, dict):
                            writer.writerow([
                                dimension,
                                member,
                                sample.get('concept', 'N/A'),
                                sample.get('value', 'N/A')
                            ])
                            segment_rows += 1
        
        print(f"✅ Created tesla_segment_breakdown.csv with {segment_rows} segment examples")
        
        return True
        
    except FileNotFoundError:
        print("❌ merged_sec_data.json not found. The data hasn't been fetched yet.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def show_sheets_instructions():
    """Show simple instructions for Google Sheets"""
    
    print("\n" + "="*60)
    print("📊 VIEW DATA IN GOOGLE SHEETS - SIMPLE METHOD")
    print("="*60)
    
    print("""
OPTION 1: Quick Import (No Setup Required)
=========================================
1. Go to Google Sheets: https://sheets.google.com
2. Create new spreadsheet
3. File → Import → Upload
4. Choose: tesla_financial_summary.csv
5. Import data → Replace spreadsheet

You'll immediately see:
- Key financial metrics (Revenue, Net Income, etc.)
- Segment dimension summary
- All values formatted for easy reading

OPTION 2: Full Integration (Requires Setup)
==========================================
To get the full automated pipeline with daily updates:

1. First install Python packages:
   pip3 install requests pandas beautifulsoup4 pdfplumber

2. Then run the enhanced fetcher:
   python3 fetch_sec_facts.py

3. Set up Google Cloud (if you have access):
   - Enable BigQuery API
   - Run: gcloud auth login
   - Run: ./setup_bigquery.sh

4. Add Apps Script to Google Sheets:
   - Copy code from apps_script/ folder
   - Connect to BigQuery
   - Use SEC Analysis menu

For now, the CSV files give you immediate access to the data!
""")

def main():
    print("🔍 SEC Data Viewer - Using Existing Data")
    print("="*40)
    
    if create_financial_summary():
        show_sheets_instructions()
        
        print("\n📈 Sample of what you'll see in Google Sheets:")
        print("-" * 40)
        
        # Show preview of CSV content
        try:
            with open('tesla_financial_summary.csv', 'r') as f:
                lines = f.readlines()[:10]
                for line in lines:
                    print(line.strip())
        except:
            pass

if __name__ == "__main__":
    main()