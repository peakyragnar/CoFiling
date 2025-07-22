"""Unit tests for SEC data extraction"""
import unittest
import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ingestion.sec_fetcher import SECFetcher
from extraction.xbrl_parser import XBRLParser
from validation.sec_validator import SECValidator


class TestSECExtraction(unittest.TestCase):
    """Test SEC data extraction functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        cls.test_cik = "0001318605"  # Tesla
        cls.output_dir = Path(__file__).parent.parent / 'output'
        
    def test_sec_fetcher_import(self):
        """Test that SECFetcher can be imported"""
        fetcher = SECFetcher()
        self.assertIsNotNone(fetcher)
        self.assertTrue(hasattr(fetcher, 'fetch_company_facts'))
        
    def test_xbrl_parser_import(self):
        """Test that XBRLParser can be imported"""
        parser = XBRLParser()
        self.assertIsNotNone(parser)
        self.assertTrue(hasattr(parser, 'parse_company_facts'))
        
    def test_load_existing_data(self):
        """Test loading existing SEC data files"""
        # Check for existing output files
        raw_file = self.output_dir / f'raw_sec_facts_{self.test_cik}.json'
        formatted_file = self.output_dir / f'formatted_sec_data_{self.test_cik}.json'
        
        if raw_file.exists():
            with open(raw_file, 'r') as f:
                raw_data = json.load(f)
            
            # Verify basic structure
            self.assertIn('cik', raw_data)
            self.assertIn('entityName', raw_data)
            self.assertIn('facts', raw_data)
            
            # Check facts structure
            facts = raw_data.get('facts', {}).get('us-gaap', {})
            self.assertGreater(len(facts), 100, "Should have at least 100 concepts")
            
        if formatted_file.exists():
            with open(formatted_file, 'r') as f:
                formatted_data = json.load(f)
            
            # Verify formatted structure
            self.assertIn('metadata', formatted_data)
            self.assertIn('structured', formatted_data)
            
            # Check structured data
            structured = formatted_data.get('structured', {})
            self.assertIn('facts', structured)
            self.assertIn('segments', structured)
            
    def test_validation_with_existing_data(self):
        """Test validation on existing data"""
        raw_file = self.output_dir / f'raw_sec_facts_{self.test_cik}.json'
        formatted_file = self.output_dir / f'formatted_sec_data_{self.test_cik}.json'
        
        if raw_file.exists() and formatted_file.exists():
            with open(raw_file, 'r') as f:
                raw_data = json.load(f)
            with open(formatted_file, 'r') as f:
                formatted_data = json.load(f)
            
            # Run validation
            validator = SECValidator()
            report = validator.validate_extraction(raw_data, formatted_data)
            
            # Check validation report structure
            self.assertIn('is_complete', report)
            self.assertIn('completeness_score', report)
            self.assertIn('summary', report)
            self.assertIn('detailed_checks', report)
            self.assertIn('recommendations', report)
            
            # Check summary
            summary = report['summary']
            self.assertGreater(summary['total_concepts'], 100)
            self.assertGreater(summary['total_facts'], 500)
            self.assertGreater(summary['segment_dimensions'], 10)
            
            # Print report for inspection
            print("\nValidation Report Summary:")
            print(f"Company: {summary['company']}")
            print(f"CIK: {summary['cik']}")
            print(f"Total Concepts: {summary['total_concepts']:,}")
            print(f"Total Facts: {summary['total_facts']:,}")
            print(f"Segment Dimensions: {summary['segment_dimensions']}")
            print(f"Completeness Score: {report['completeness_score']:.2%}")
            print(f"Is Complete: {report['is_complete']}")
            
            if report['recommendations']:
                print("\nRecommendations:")
                for rec in report['recommendations']:
                    print(f"  - {rec}")
    
    def test_expected_values_for_tesla(self):
        """Test that Tesla data meets expected values"""
        formatted_file = self.output_dir / f'formatted_sec_data_{self.test_cik}.json'
        
        if formatted_file.exists():
            with open(formatted_file, 'r') as f:
                formatted_data = json.load(f)
            
            # Check metadata
            metadata = formatted_data.get('metadata', {})
            self.assertEqual(str(metadata.get('cik')), "1318605")
            self.assertIn("Tesla", metadata.get('entityName', ''))
            
            # Check facts count
            facts = formatted_data.get('structured', {}).get('facts', {})
            self.assertGreaterEqual(len(facts), 600, "Tesla should have at least 600 fact concepts")
            
            # Check for specific Tesla segments
            segments = formatted_data.get('structured', {}).get('segments', {})
            self.assertGreaterEqual(len(segments), 20, "Tesla should have at least 20 segment dimensions")
            
            # Check for automotive segment (Tesla-specific)
            has_product_segment = any('Product' in dim for dim in segments.keys())
            self.assertTrue(has_product_segment, "Tesla should have product/service segments")


class TestDataCompleteness(unittest.TestCase):
    """Test data completeness requirements"""
    
    def test_critical_financial_items(self):
        """Test that critical financial items are defined"""
        validator = SECValidator()
        
        # Check critical items list
        self.assertIn('Revenues', validator.CRITICAL_ITEMS)
        self.assertIn('Assets', validator.CRITICAL_ITEMS)
        self.assertIn('Liabilities', validator.CRITICAL_ITEMS)
        self.assertIn('NetIncomeLoss', validator.CRITICAL_ITEMS)
        
    def test_segment_expectations(self):
        """Test segment dimension expectations"""
        validator = SECValidator()
        
        # Check expected segments
        self.assertIn('StatementBusinessSegmentsAxis', validator.EXPECTED_SEGMENTS)
        self.assertIn('ProductOrServiceAxis', validator.EXPECTED_SEGMENTS)


if __name__ == '__main__':
    unittest.main()