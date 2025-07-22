#!/usr/bin/env python3
"""
Main entry point for SEC Filing Analysis System
Usage: python main.py --cik 1318605 --pdf tsla_q1_2025_earnings.pdf
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ingestion.sec_fetcher import SECFetcher
from extraction.xbrl_parser import XBRLParser
from validation.sec_validator import SECValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='SEC Filing Analysis System')
    parser.add_argument('--cik', required=True, help='Company CIK (e.g., 1318605 for Tesla)')
    parser.add_argument('--pdf', help='Path to earnings PDF (optional for now)')
    parser.add_argument('--output-dir', default='output', help='Output directory for results')
    parser.add_argument('--years', type=int, default=5, help='Number of full years to include (default: 5)')
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    logger.info(f"Starting SEC data extraction for CIK: {args.cik}")
    
    # Step 1: Fetch SEC data
    logger.info("Fetching SEC company facts...")
    fetcher = SECFetcher()
    raw_data = fetcher.fetch_company_facts(args.cik)
    
    if not raw_data:
        logger.error("Failed to fetch SEC data")
        return 1
    
    # Save raw data
    raw_file = output_dir / f'raw_sec_facts_{args.cik}.json'
    with open(raw_file, 'w') as f:
        json.dump(raw_data, f, indent=2)
    logger.info(f"Raw data saved to {raw_file}")
    
    # Step 2: Parse and structure the data
    logger.info(f"Parsing XBRL data (last {args.years} full years + current year)...")
    parser = XBRLParser()
    formatted_data = parser.parse_company_facts(raw_data, years_back=args.years)
    
    # Save formatted data
    formatted_file = output_dir / f'formatted_sec_data_{args.cik}.json'
    with open(formatted_file, 'w') as f:
        json.dump(formatted_data, f, indent=2)
    logger.info(f"Formatted data saved to {formatted_file}")
    
    # Step 3: Validate completeness
    validator = SECValidator()
    validation_results = validator.validate_extraction(raw_data, formatted_data)
    
    # Save validation report
    validation_file = output_dir / f'validation_report_{args.cik}.json'
    with open(validation_file, 'w') as f:
        json.dump(validation_results, f, indent=2)
    
    # Print summary
    print_extraction_summary(formatted_data, validation_results)
    
    # Step 4: Process PDF if provided
    pdf_data = None
    if args.pdf:
        logger.info(f"Processing earnings PDF: {args.pdf}")
        
        # Check if Gemini is available
        use_gemini = bool(os.environ.get('GOOGLE_API_KEY'))
        
        if use_gemini:
            from ai.gemini_client import GeminiPDFParser
            pdf_parser = GeminiPDFParser()
            logger.info("Using Gemini-enhanced PDF parsing")
        else:
            from extraction.earnings_parser import EarningsParser
            pdf_parser = EarningsParser()
            logger.info("Using traditional PDF parsing (set GOOGLE_API_KEY for enhanced parsing)")
        
        pdf_data = pdf_parser.parse_earnings_pdf(args.pdf)
        
        # Save PDF data
        pdf_file = output_dir / f'earnings_data_{args.cik}.json'
        with open(pdf_file, 'w') as f:
            json.dump(pdf_data, f, indent=2)
        logger.info(f"PDF data saved to {pdf_file}")
        
        # Show PDF extraction summary
        if 'extraction_summary' in pdf_data:
            print_pdf_summary(pdf_data)
    
    return 0 if validation_results['is_complete'] else 1




def print_extraction_summary(formatted_data, validation_results):
    """Print a summary of the extraction results"""
    print("\n" + "="*60)
    print("SEC EXTRACTION SUMMARY")
    print("="*60)
    
    # Company info
    summary = validation_results.get('summary', {})
    print(f"\nCompany: {summary.get('company', 'Unknown')}")
    print(f"CIK: {summary.get('cik', 'Unknown')}")
    
    # Data summary
    print(f"\nData Extracted:")
    print(f"  - Total concepts: {summary.get('total_concepts', 0):,}")
    print(f"  - Total facts: {summary.get('total_facts', 0):,}")
    print(f"  - Segment dimensions: {summary.get('segment_dimensions', 0)}")
    print(f"  - Segment facts: {summary.get('segment_facts', 0):,}")
    print(f"  - Unique periods: {summary.get('unique_periods', 0)}")
    
    # Period coverage
    period_coverage = summary.get('period_coverage', {})
    if period_coverage:
        print(f"\nPeriod Coverage:")
        print(f"  - Year range: {period_coverage.get('year_range', 'N/A')}")
        print(f"  - Total years: {period_coverage.get('total_years', 0)}")
        print(f"  - Quarterly periods: {period_coverage.get('quarters_count', 0)}")
    
    # Validation checks
    print(f"\nValidation Results:")
    checks = validation_results.get('detailed_checks', {})
    
    # Basic checks
    for check in ['has_minimum_concepts', 'has_minimum_facts', 'has_segments', 'has_minimum_segments']:
        if check in checks:
            status = "✓" if checks[check] else "✗"
            print(f"  {status} {check.replace('_', ' ').title()}")
    
    # Critical items summary
    if 'critical_items' in checks and '_summary' in checks['critical_items']:
        summary_info = checks['critical_items']['_summary']
        print(f"\nCritical Financial Items:")
        print(f"  - Found: {summary_info['found']}/{summary_info['total']} ({summary_info['percentage']:.0f}%)")
    
    # Segment coverage
    if 'segment_coverage' in checks and '_summary' in checks['segment_coverage']:
        seg_summary = checks['segment_coverage']['_summary']
        print(f"\nSegment Coverage:")
        print(f"  - Expected segments found: {seg_summary['found']}/{seg_summary['expected']}")
        print(f"  - Additional segments: {seg_summary['additional']}")
    
    # Completeness score
    print(f"\nCompleteness Score: {validation_results.get('completeness_score', 0):.1%}")
    
    # Recommendations
    if validation_results.get('recommendations'):
        print(f"\nRecommendations:")
        for rec in validation_results['recommendations']:
            print(f"  - {rec}")
    
    # Overall status
    print(f"\nOverall Status: {'✓ COMPLETE' if validation_results.get('is_complete') else '✗ INCOMPLETE'}")
    print("="*60 + "\n")


def print_pdf_summary(pdf_data: dict):
    """Print summary of PDF extraction results"""
    print("\n" + "="*60)
    print("PDF EXTRACTION SUMMARY")
    print("="*60)
    
    summary = pdf_data.get('extraction_summary', {})
    
    # Show what was found
    print("\nData Extracted:")
    print(f"  ✓ Vehicle metrics" if summary.get('vehicle_metrics_found') else "  ✗ Vehicle metrics")
    print(f"  ✓ Energy metrics" if summary.get('energy_metrics_found') else "  ✗ Energy metrics")
    print(f"  ✓ Financial segments" if summary.get('financial_segments_found') else "  ✗ Financial segments")
    print(f"  ✓ Margins" if summary.get('margins_found') else "  ✗ Margins")
    
    if summary.get('gemini_enhanced'):
        print(f"\n  🤖 Gemini Vision processed {summary.get('gemini_pages_processed', 0)} pages")
    
    # Show key metrics
    if pdf_data.get('vehicle_metrics', {}).get('deliveries'):
        print("\nVehicle Deliveries Found:")
        for model, data in pdf_data['vehicle_metrics']['deliveries'].items():
            if isinstance(data, dict):
                print(f"  - {model}: {data.get('value', 'N/A'):,}")
    
    if pdf_data.get('energy_metrics', {}).get('storage_deployed_gwh'):
        value = pdf_data['energy_metrics']['storage_deployed_gwh']
        if isinstance(value, dict):
            print(f"\nEnergy Storage: {value.get('value', 'N/A')} GWh")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    sys.exit(main())