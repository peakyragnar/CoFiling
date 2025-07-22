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

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ingestion.sec_fetcher import SECFetcher
from extraction.xbrl_parser import XBRLParser
from validation.sec_validator import SECValidator
from validation.generic_pdf_validator import GenericPDFValidator

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
            from extraction.generic_parser import GenericEarningsParser
            from ai.gemini_client import GeminiClient
            
            gemini_client = GeminiClient()
            pdf_parser = GenericEarningsParser(use_gemini=True)
            logger.info("Using Gemini-enhanced generic PDF parsing")
            pdf_data = pdf_parser.parse_earnings_pdf(args.pdf, gemini_client)
        else:
            from extraction.generic_parser import GenericEarningsParser
            pdf_parser = GenericEarningsParser(use_gemini=False)
            logger.info("Using traditional PDF parsing (set GOOGLE_API_KEY for enhanced parsing)")
            pdf_data = pdf_parser.parse_earnings_pdf(args.pdf)
        
        # Save PDF data
        pdf_file = output_dir / f'earnings_data_{args.cik}.json'
        with open(pdf_file, 'w') as f:
            json.dump(pdf_data, f, indent=2)
        logger.info(f"PDF data saved to {pdf_file}")
        
        # Validate PDF extraction
        pdf_validator = GenericPDFValidator()
        pdf_validation = pdf_validator.validate_extraction(pdf_data)
        
        # Save PDF validation report
        pdf_validation_file = output_dir / f'pdf_validation_report_{args.cik}.json'
        with open(pdf_validation_file, 'w') as f:
            json.dump(pdf_validation, f, indent=2)
        
        # Show PDF extraction summary
        print_pdf_summary(pdf_data, pdf_validation)
    
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


def print_pdf_summary(pdf_data: dict, validation_results: dict):
    """Print summary of PDF extraction and validation results"""
    print("\n" + "="*60)
    print("PDF EXTRACTION SUMMARY")
    print("="*60)
    
    # Extract summary info
    summary = validation_results.get('summary', {})
    print(f"\nCompany: {summary.get('company', 'Unknown')}")
    print(f"Period: {summary.get('period', 'Unknown')}")
    print(f"Business Model: {summary.get('business_model', 'Unknown')}")
    print(f"Extraction Method: {summary.get('extraction_method', 'Unknown')}")
    print(f"Data Points Extracted: {summary.get('data_points_extracted', 0)}")
    
    # Structure validation
    structure_check = validation_results.get('detailed_checks', {}).get('structure', {})
    if structure_check:
        print("\nData Structure:")
        print(f"  - Hierarchical Data: {'✓' if structure_check.get('has_hierarchical_data') else '✗'}")
        print(f"  - Flat Metrics: {'✓' if structure_check.get('has_flat_metrics') else '✗'}")
        print(f"  - Time Series: {'✓' if structure_check.get('has_time_series') else '✗'}")
        if structure_check.get('hierarchical_categories'):
            print(f"  - Categories: {', '.join(structure_check['hierarchical_categories'])}")
    
    # Completeness check
    completeness_check = validation_results.get('detailed_checks', {}).get('completeness', {})
    if completeness_check.get('expected_vs_extracted'):
        exp_vs_ext = completeness_check['expected_vs_extracted']
        print(f"\nExtraction Completeness:")
        print(f"  - Expected Data Points: {exp_vs_ext.get('expected', 0)}")
        print(f"  - Extracted Data Points: {exp_vs_ext.get('extracted', 0)}")
        print(f"  - Extraction Rate: {completeness_check.get('extraction_rate', 0):.1%}")
    
    # Hierarchy validation
    hierarchy_check = validation_results.get('detailed_checks', {}).get('hierarchies', {})
    if hierarchy_check.get('_summary'):
        h_summary = hierarchy_check['_summary']
        print(f"\nHierarchical Data Validation:")
        print(f"  - Total Hierarchies: {h_summary.get('total_hierarchies', 0)}")
        print(f"  - Valid Hierarchies: {h_summary.get('valid_hierarchies', 0)}")
        if hierarchy_check.get('validation_errors'):
            print(f"  - Errors: {', '.join(hierarchy_check['validation_errors'][:2])}")
    
    # Display some actual extracted data
    print("\nSample Extracted Data:")
    
    # Get the actual data from the generic structure
    if isinstance(pdf_data, dict) and 'data' in pdf_data:
        actual_data = pdf_data['data']
    else:
        actual_data = pdf_data
    
    # Show hierarchical data samples
    if 'hierarchical_data' in actual_data:
        for category, cat_data in actual_data['hierarchical_data'].items():
            if isinstance(cat_data, dict):
                print(f"\n  {category.title()}:")
                sample_count = 0
                for key, value in cat_data.items():
                    if sample_count >= 3:  # Show only 3 samples per category
                        break
                    if isinstance(value, dict) and 'value' in value:
                        print(f"    - {key}: {value['value']} {value.get('unit', '')}")
                        sample_count += 1
    
    # Show flat metrics samples
    if 'flat_metrics' in actual_data and actual_data['flat_metrics']:
        print("\n  Operational Metrics:")
        sample_count = 0
        for metric_name, metric_data in actual_data['flat_metrics'].items():
            if sample_count >= 3:
                break
            if isinstance(metric_data, dict) and metric_data.get('value') is not None:
                value = metric_data['value']
                unit = metric_data.get('unit', '')
                print(f"    - {metric_name}: {value:,.0f if isinstance(value, (int, float)) else value} {unit}")
                sample_count += 1
    
    # Data quality summary
    quality = validation_results.get('data_quality', {})
    if quality:
        print(f"\nData Quality:")
        print(f"  - Numeric Data Valid: {'✓' if quality.get('numeric_data_valid') else '✗'}")
        print(f"  - Units Consistent: {'✓' if quality.get('units_consistent') else '✗'}")
        if quality.get('average_confidence'):
            print(f"  - Average Confidence: {quality['average_confidence']:.2f}")
        if quality.get('issues'):
            print(f"  - Issues Found: {len(quality['issues'])}")
    
    # Completeness score
    print(f"\nOverall Completeness: {validation_results.get('completeness_score', 0):.1%}")
    
    # Recommendations
    if validation_results.get('recommendations'):
        print(f"\nRecommendations:")
        for i, rec in enumerate(validation_results['recommendations'][:3]):
            print(f"  {i+1}. {rec}")
    
    # Overall status
    print(f"\nStatus: {'✓ EXTRACTION COMPLETE' if validation_results.get('is_complete') else '✗ EXTRACTION INCOMPLETE'}")
    print("="*60 + "\n")


if __name__ == "__main__":
    sys.exit(main())