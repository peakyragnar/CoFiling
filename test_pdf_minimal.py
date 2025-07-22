#!/usr/bin/env python3
"""
Minimal test - extract from just page 4 which has the key financial data
"""
import json
import logging
from src.ai.gemini_client import GeminiClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Less verbose

print("Testing minimal PDF extraction (page 4 only)...")
print("=" * 60)

# Initialize Gemini client
client = GeminiClient()

# Extract from just page 4
try:
    result = client.extract_pdf_data(
        "TSLA-Q1-2025-Update.pdf",
        page_numbers=[4]  # Just the page with financial data
    )
    
    # Save result
    with open("output/test_minimal_extraction.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nExtraction complete!")
    print(f"Values extracted: {len(result.get('extracted_values', []))}")
    
    # Show extracted data
    if result.get('raw_extractions'):
        for extraction in result['raw_extractions']:
            print(f"\nExtracted from page {extraction.get('page_number', '?')}:")
            
            # Pretty print the extraction
            for key, value in extraction.items():
                if key != 'page_number' and value:
                    print(f"\n  {key}:")
                    if isinstance(value, dict):
                        for k, v in value.items():
                            if v:
                                print(f"    {k}: {v}")
                    else:
                        print(f"    {value}")
    
    print("\nFull results saved to output/test_minimal_extraction.json")
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()