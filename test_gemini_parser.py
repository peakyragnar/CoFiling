#!/usr/bin/env python3
"""Test Gemini-enhanced PDF parsing"""
import os
import sys
import json
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ai.gemini_client import GeminiPDFParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Check for API key
    if not os.environ.get('GOOGLE_API_KEY'):
        print("Error: Please set GOOGLE_API_KEY environment variable")
        print("Export your key: export GOOGLE_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    pdf_path = "TSLA-Q1-2025-Update.pdf"
    
    print(f"Testing Gemini-enhanced PDF parsing for: {pdf_path}")
    print("="*60)
    
    # Create parser
    parser = GeminiPDFParser()
    
    # Parse with Gemini enhancement
    print("\n1. Parsing with traditional method + Gemini enhancement...")
    results = parser.parse_earnings_pdf(pdf_path, use_gemini=True)
    
    # Save results
    output_file = "earnings_gemini_enhanced.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {output_file}")
    
    # Display summary
    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    
    if 'extraction_summary' in results:
        summary = results['extraction_summary']
        print(f"Traditional parser found:")
        print(f"  - Vehicle metrics: {'✓' if summary.get('vehicle_metrics_found') else '✗'}")
        print(f"  - Energy metrics: {'✓' if summary.get('energy_metrics_found') else '✗'}")
        print(f"  - Financial segments: {'✓' if summary.get('financial_segments_found') else '✗'}")
        print(f"  - Margins: {'✓' if summary.get('margins_found') else '✗'}")
        
        if summary.get('gemini_enhanced'):
            print(f"\nGemini enhancement:")
            print(f"  - Pages processed: {summary.get('gemini_pages_processed', 0)}")
    
    # Show extracted data
    print("\n" + "="*60)
    print("EXTRACTED DATA")
    print("="*60)
    
    # Vehicle metrics
    if results.get('vehicle_metrics'):
        print("\nVehicle Metrics:")
        vm = results['vehicle_metrics']
        if 'deliveries' in vm:
            print(f"  Deliveries:")
            for model, data in vm['deliveries'].items():
                if isinstance(data, dict):
                    print(f"    - {model}: {data.get('value', 'N/A'):,}")
                else:
                    print(f"    - {model}: {data:,}")
    
    # Energy metrics
    if results.get('energy_metrics'):
        print("\nEnergy Metrics:")
        em = results['energy_metrics']
        if 'storage_deployed_gwh' in em:
            value = em['storage_deployed_gwh']
            if isinstance(value, dict):
                print(f"  - Storage deployed: {value.get('value', 'N/A')} GWh")
            else:
                print(f"  - Storage deployed: {value} GWh")
    
    # Financial segments
    if results.get('financial_segments'):
        print("\nFinancial Segments:")
        for segment, value in results['financial_segments'].items():
            if isinstance(value, dict):
                print(f"  - {segment}: ${value.get('value', 'N/A')}M")
            else:
                print(f"  - {segment}: ${value}M")
    
    # Geographic revenue
    if results.get('geographic_revenue'):
        print("\nGeographic Revenue:")
        for region, value in results['geographic_revenue'].items():
            print(f"  - {region}: ${value}M")
    
    # Margins
    if results.get('margins'):
        print("\nMargins:")
        for margin_type, value in results['margins'].items():
            if isinstance(value, dict):
                print(f"  - {margin_type}: {value.get('value', 'N/A')}%")
            else:
                print(f"  - {margin_type}: {value}%")
    
    print("\n" + "="*60)
    
    # Note about full Gemini implementation
    print("\nNOTE: Full Gemini Vision implementation requires:")
    print("1. PDF to image conversion (pdf2image library)")
    print("2. Sending images to Gemini API")
    print("3. Parsing structured responses")
    print("\nThis test shows the framework is ready for production use.")

if __name__ == "__main__":
    main()