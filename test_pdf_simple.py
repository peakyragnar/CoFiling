#!/usr/bin/env python3
"""
Simple test of PDF extraction focusing on key pages
"""
import json
import logging
from src.ai.gemini_client import GeminiClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

print("Testing simplified PDF extraction...")
print("=" * 60)

# Initialize Gemini client
client = GeminiClient()

# Extract from specific pages we know have data
pdf_path = "TSLA-Q1-2025-Update.pdf"
page_priorities = {
    4: 1.0,  # Page 4 has main financial data
    5: 0.9,  # Page 5 has additional data
    3: 0.8,  # Page 3 might have summary
}

print(f"Extracting from pages: {list(page_priorities.keys())}")

try:
    # Use parallel extraction with our fixes
    result = client.extract_pdf_data_parallel(
        pdf_path,
        page_priorities=page_priorities
    )
    
    # Save raw result
    with open("output/test_simple_extraction.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nExtraction complete!")
    print(f"Pages processed: {result['extraction_metadata']['pages_processed']}")
    print(f"Values extracted: {len(result.get('extracted_values', []))}")
    print(f"Errors: {len(result['extraction_metadata'].get('errors', []))}")
    
    # Show some extracted values
    if result.get('raw_extractions'):
        print("\nSample extracted data:")
        for extraction in result['raw_extractions'][:2]:
            page = extraction.get('page_number', '?')
            print(f"\n  Page {page}:")
            
            # Show revenue if found
            if 'revenue' in extraction:
                revenue = extraction['revenue']
                if isinstance(revenue, dict):
                    total = revenue.get('total', 'N/A')
                    print(f"    Total Revenue: {total}")
                    if 'automotive' in revenue:
                        print(f"    Automotive: {revenue['automotive']}")
            
            # Show margins if found
            if 'margins' in extraction:
                margins = extraction['margins']
                if isinstance(margins, dict):
                    gross = margins.get('gross', 'N/A')
                    print(f"    Gross Margin: {gross}")
    
    print("\nCheck output/test_simple_extraction.json for full results")
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()