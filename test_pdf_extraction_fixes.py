#!/usr/bin/env python3
"""
Test PDF extraction with performance and parsing fixes
"""
import json
import logging
from pathlib import Path
from src.extraction.generic_parser import GenericEarningsParser
from src.ai.gemini_client import GeminiClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_pdf_extraction():
    """Test PDF extraction with all fixes"""
    print("Testing PDF extraction with fixes...")
    print("=" * 60)
    
    # Initialize components
    parser = GenericEarningsParser(use_gemini=True)
    gemini_client = GeminiClient()
    
    # Test with Tesla Q1 2025 PDF
    pdf_path = "TSLA-Q1-2025-Update.pdf"
    
    if not Path(pdf_path).exists():
        print(f"ERROR: PDF file not found: {pdf_path}")
        return
    
    print(f"Extracting data from: {pdf_path}")
    print("This will use:")
    print("- Rate limiting with exponential backoff")
    print("- Single worker to avoid quota issues")
    print("- Enhanced prompts with examples")
    print("- Improved value parsing")
    print("- Better error handling")
    print("-" * 60)
    
    try:
        # Run extraction
        result = parser.parse_earnings_pdf(pdf_path, gemini_client)
        
        # Save results
        output_path = "output/test_extraction_with_fixes.json"
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")
        
        # Display summary
        print("\nExtraction Summary:")
        print("-" * 40)
        
        # Check hierarchical data
        if "data" in result and "hierarchical_data" in result["data"]:
            hier_data = result["data"]["hierarchical_data"]
            
            # Financial data
            if "financial" in hier_data:
                financial = hier_data["financial"]
                
                # Revenue
                if "revenue" in financial and "total" in financial["revenue"]:
                    total_rev = financial["revenue"]["total"].get("value")
                    print(f"Total Revenue: ${total_rev}M")
                
                # Segments
                if "segments" in financial:
                    print("\nRevenue Segments:")
                    for segment, data in financial["segments"].items():
                        if isinstance(data, dict) and "value" in data:
                            print(f"  {segment}: ${data['value']}M")
                
                # Margins
                if "margins" in financial:
                    print("\nMargins:")
                    for margin_type, value in financial["margins"].items():
                        print(f"  {margin_type}: {value}%")
            
            # Geographic data
            if "geographic" in hier_data and "regions" in hier_data["geographic"]:
                print("\nGeographic Revenue:")
                for region, data in hier_data["geographic"]["regions"].items():
                    if isinstance(data, dict) and "value" in data:
                        print(f"  {region}: ${data['value']}M")
        
        # Flat metrics
        if "data" in result and "flat_metrics" in result["data"]:
            print("\nOperational Metrics:")
            for metric, data in result["data"]["flat_metrics"].items():
                if isinstance(data, dict) and "value" in data:
                    print(f"  {metric}: {data['value']} {data.get('unit', '')}")
        
        # Extraction metadata
        if "document_analysis" in result:
            analysis = result["document_analysis"]
            print(f"\nData Completeness: {analysis.get('data_completeness', 0):.1%}")
            print(f"Extraction Method: {analysis.get('extraction_method', 'unknown')}")
        
        # Check for errors
        if "data" in result and "extraction_metadata" in result["data"]:
            metadata = result["data"]["extraction_metadata"]
            if metadata.get("errors"):
                print(f"\nErrors encountered: {len(metadata['errors'])}")
                for error in metadata["errors"][:3]:
                    print(f"  - Page {error.get('page')}: {error.get('error')}")
        
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"\nERROR during extraction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_extraction()