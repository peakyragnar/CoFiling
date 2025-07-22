"""Smart PDF parser for earnings reports with table and image extraction"""
import pdfplumber
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class EarningsParser:
    """
    Parser for earnings PDFs that extracts:
    - Structured tables
    - Text near key metrics
    - Image-based data (charts/graphs)
    """
    
    # Key metrics we're looking for
    TARGET_METRICS = {
        'vehicle_production': ['production', 'produced', 'manufacturing'],
        'vehicle_deliveries': ['deliveries', 'delivered', 'delivery'],
        'model_breakdown': ['model 3', 'model y', 'model s', 'model x', 'cybertruck'],
        'energy_storage': ['gwh', 'mwh', 'storage deploy', 'megapack', 'powerwall'],
        'revenue_segments': ['automotive', 'energy', 'services', 'revenue'],
        'geographic': ['united states', 'china', 'europe', 'other', 'region'],
        'margins': ['gross margin', 'operating margin', 'automotive gross margin']
    }
    
    def __init__(self):
        self.extracted_data = {
            'vehicle_metrics': {},
            'energy_metrics': {},
            'financial_segments': {},
            'geographic_segments': {},
            'margins': {},
            'metadata': {}
        }
    
    def parse_earnings_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Main parsing function that handles both tables and visual elements
        """
        logger.info(f"Parsing earnings PDF: {pdf_path}")
        
        with pdfplumber.open(pdf_path) as pdf:
            self.extracted_data['metadata'] = {
                'total_pages': len(pdf.pages),
                'file_name': Path(pdf_path).name
            }
            
            # Process each page
            for page_num, page in enumerate(pdf.pages, 1):
                logger.info(f"Processing page {page_num}")
                
                # Extract text for context
                page_text = page.extract_text() or ""
                
                # Extract tables
                tables = page.extract_tables()
                if tables:
                    self._process_tables(tables, page_num, page_text)
                
                # Look for metrics in text (for image-based slides)
                self._extract_metrics_from_text(page_text, page_num)
                
                # Check for visual elements (charts/graphs)
                self._identify_visual_elements(page, page_num)
        
        # Post-process to clean and validate data
        self._post_process_data()
        
        return self.extracted_data
    
    def _process_tables(self, tables: List[List[List[str]]], page_num: int, context: str):
        """Process extracted tables to find key metrics"""
        for table_idx, table in enumerate(tables):
            if not table or len(table) < 2:
                continue
            
            # Analyze table content
            table_str = str(table).lower()
            
            # Vehicle production/deliveries table
            if any(metric in table_str for metric in ['production', 'deliveries', 'model']):
                self._extract_vehicle_metrics(table, page_num)
            
            # Energy metrics table
            elif any(metric in table_str for metric in ['gwh', 'mwh', 'storage', 'solar']):
                self._extract_energy_metrics(table, page_num)
            
            # Financial segments table
            elif 'revenue' in table_str and any(seg in table_str for seg in ['automotive', 'energy']):
                self._extract_financial_segments(table, page_num)
            
            # Geographic segments
            elif any(region in table_str for region in ['united states', 'china', 'europe']):
                self._extract_geographic_segments(table, page_num)
    
    def _extract_vehicle_metrics(self, table: List[List[str]], page_num: int):
        """Extract vehicle production and delivery numbers"""
        logger.info(f"Extracting vehicle metrics from page {page_num}")
        
        headers = table[0] if table else []
        
        for row_idx, row in enumerate(table[1:], 1):
            if not row or len(row) < 2:
                continue
            
            row_text = ' '.join(str(cell).lower() for cell in row if cell)
            
            # Look for Model 3/Y data
            if 'model 3' in row_text or 'model y' in row_text or '3/y' in row_text:
                self._parse_vehicle_row(row, headers, 'Model 3/Y', page_num)
            
            # Look for Model S/X data
            elif 'model s' in row_text or 'model x' in row_text or 's/x' in row_text:
                self._parse_vehicle_row(row, headers, 'Model S/X', page_num)
            
            # Look for total production/deliveries
            elif 'total' in row_text and any(m in row_text for m in ['production', 'deliveries']):
                self._parse_vehicle_row(row, headers, 'Total', page_num)
    
    def _parse_vehicle_row(self, row: List[str], headers: List[str], model: str, page_num: int):
        """Parse a row of vehicle data"""
        # Find the most recent quarter (usually last non-percentage column)
        for i in range(len(row) - 1, 0, -1):
            cell = str(row[i]).strip()
            # Check if it's a number (not percentage)
            if cell and not cell.endswith('%') and self._is_number(cell):
                metric_type = 'production' if 'production' in str(row[0]).lower() else 'deliveries'
                
                if metric_type not in self.extracted_data['vehicle_metrics']:
                    self.extracted_data['vehicle_metrics'][metric_type] = {}
                
                self.extracted_data['vehicle_metrics'][metric_type][model] = {
                    'value': self._parse_number(cell),
                    'page': page_num,
                    'quarter': headers[i] if i < len(headers) else 'Q1-2025'
                }
                break
    
    def _extract_energy_metrics(self, table: List[List[str]], page_num: int):
        """Extract energy storage and solar deployment metrics"""
        logger.info(f"Extracting energy metrics from page {page_num}")
        
        for row in table:
            if not row:
                continue
            
            row_text = ' '.join(str(cell).lower() for cell in row if cell)
            
            # Storage deployments
            if 'storage' in row_text and 'gwh' in row_text:
                for cell in row:
                    if self._is_number(str(cell)) and not str(cell).endswith('%'):
                        self.extracted_data['energy_metrics']['storage_deployed_gwh'] = {
                            'value': self._parse_number(cell),
                            'page': page_num
                        }
                        break
            
            # Solar deployments
            elif 'solar' in row_text and 'mw' in row_text:
                for cell in row:
                    if self._is_number(str(cell)) and not str(cell).endswith('%'):
                        self.extracted_data['energy_metrics']['solar_deployed_mw'] = {
                            'value': self._parse_number(cell),
                            'page': page_num
                        }
                        break
    
    def _extract_financial_segments(self, table: List[List[str]], page_num: int):
        """Extract revenue by segment"""
        logger.info(f"Extracting financial segments from page {page_num}")
        
        headers = table[0] if table else []
        
        for row in table[1:]:
            if not row or len(row) < 2:
                continue
            
            row_label = str(row[0]).lower()
            
            # Automotive revenue
            if 'automotive' in row_label and 'revenue' in row_label:
                self._extract_segment_value(row, headers, 'automotive_revenue', page_num)
            
            # Energy revenue
            elif 'energy' in row_label and 'revenue' in row_label:
                self._extract_segment_value(row, headers, 'energy_revenue', page_num)
            
            # Services revenue
            elif 'services' in row_label:
                self._extract_segment_value(row, headers, 'services_revenue', page_num)
            
            # Gross margins
            elif 'gross margin' in row_label:
                if 'automotive' in row_label:
                    self._extract_margin_value(row, headers, 'automotive_gross_margin', page_num)
                elif 'total' in row_label:
                    self._extract_margin_value(row, headers, 'total_gross_margin', page_num)
    
    def _extract_segment_value(self, row: List[str], headers: List[str], segment_name: str, page_num: int):
        """Extract a segment revenue value"""
        # Find the most recent quarter value
        for i in range(len(row) - 1, 0, -1):
            cell = str(row[i]).strip()
            if cell and not cell.endswith('%') and self._is_number(cell):
                self.extracted_data['financial_segments'][segment_name] = {
                    'value': self._parse_number(cell),
                    'page': page_num,
                    'quarter': headers[i] if i < len(headers) else 'Q1-2025',
                    'unit': 'millions'
                }
                break
    
    def _extract_margin_value(self, row: List[str], headers: List[str], margin_name: str, page_num: int):
        """Extract a margin percentage"""
        for i in range(len(row) - 1, 0, -1):
            cell = str(row[i]).strip()
            if cell and '%' in cell:
                self.extracted_data['margins'][margin_name] = {
                    'value': self._parse_percentage(cell),
                    'page': page_num,
                    'quarter': headers[i] if i < len(headers) else 'Q1-2025'
                }
                break
    
    def _extract_geographic_segments(self, table: List[List[str]], page_num: int):
        """Extract geographic revenue breakdown"""
        logger.info(f"Extracting geographic segments from page {page_num}")
        
        # Implementation would be similar to financial segments
        # but looking for geographic regions
        pass
    
    def _extract_metrics_from_text(self, text: str, page_num: int):
        """
        Extract metrics from text that might be in image-based slides
        This handles cases where data is in images/charts
        """
        if not text:
            return
        
        # Look for patterns like "4.0 GWh" or "Model 3/Y: 345,454"
        
        # Energy storage pattern
        gwh_pattern = r'(\d+\.?\d*)\s*GWh'
        gwh_matches = re.findall(gwh_pattern, text, re.IGNORECASE)
        if gwh_matches and 'storage_deployed_gwh' not in self.extracted_data['energy_metrics']:
            self.extracted_data['energy_metrics']['storage_deployed_gwh'] = {
                'value': float(gwh_matches[0]),
                'page': page_num,
                'source': 'text_extraction'
            }
        
        # Vehicle delivery patterns
        delivery_pattern = r'deliver(?:ies|ed)\s*:?\s*([\d,]+)'
        delivery_matches = re.findall(delivery_pattern, text, re.IGNORECASE)
        if delivery_matches:
            value = self._parse_number(delivery_matches[0])
            if value > 1000:  # Sanity check
                self.extracted_data['vehicle_metrics']['total_deliveries'] = {
                    'value': value,
                    'page': page_num,
                    'source': 'text_extraction'
                }
    
    def _identify_visual_elements(self, page, page_num: int):
        """
        Identify pages with charts/graphs that might need special handling
        """
        # Check for image objects
        if hasattr(page, 'images') and page.images:
            logger.info(f"Page {page_num} contains {len(page.images)} images/charts")
            
            # Mark pages with significant visual content
            if 'pages_with_visuals' not in self.extracted_data['metadata']:
                self.extracted_data['metadata']['pages_with_visuals'] = []
            
            self.extracted_data['metadata']['pages_with_visuals'].append({
                'page': page_num,
                'image_count': len(page.images),
                'note': 'May contain charts with additional data'
            })
    
    def _is_number(self, text: str) -> bool:
        """Check if text represents a number"""
        if not text:
            return False
        # Remove commas and check
        cleaned = text.replace(',', '').replace('$', '').strip()
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    
    def _parse_number(self, text: str) -> float:
        """Parse a number from text, handling commas and formatting"""
        if not text:
            return 0.0
        cleaned = str(text).replace(',', '').replace('$', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def _parse_percentage(self, text: str) -> float:
        """Parse a percentage value"""
        if not text:
            return 0.0
        cleaned = str(text).replace('%', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def _post_process_data(self):
        """Clean and validate extracted data"""
        # Add extraction summary
        self.extracted_data['extraction_summary'] = {
            'vehicle_metrics_found': len(self.extracted_data['vehicle_metrics']) > 0,
            'energy_metrics_found': len(self.extracted_data['energy_metrics']) > 0,
            'financial_segments_found': len(self.extracted_data['financial_segments']) > 0,
            'margins_found': len(self.extracted_data['margins']) > 0,
            'visual_pages': len(self.extracted_data['metadata'].get('pages_with_visuals', []))
        }
        
        # Log what we found vs what we're missing
        logger.info(f"Extraction summary: {self.extracted_data['extraction_summary']}")
        
        # Identify missing critical data
        missing = []
        if 'deliveries' not in self.extracted_data['vehicle_metrics']:
            missing.append('vehicle_deliveries')
        if 'storage_deployed_gwh' not in self.extracted_data['energy_metrics']:
            missing.append('energy_storage_gwh')
        if not self.extracted_data['geographic_segments']:
            missing.append('geographic_breakdown')
        
        if missing:
            self.extracted_data['extraction_summary']['missing_data'] = missing
            logger.warning(f"Missing critical data: {missing}")


def main():
    """Test the parser"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python earnings_parser.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    parser = EarningsParser()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    print(f"Parsing {pdf_path}...")
    results = parser.parse_earnings_pdf(pdf_path)
    
    # Save results
    output_file = "earnings_extracted_data.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nExtraction complete. Results saved to {output_file}")
    
    # Print summary
    print("\nExtraction Summary:")
    print(json.dumps(results['extraction_summary'], indent=2))
    
    # Show sample data
    if results['vehicle_metrics']:
        print("\nVehicle Metrics Found:")
        print(json.dumps(results['vehicle_metrics'], indent=2))
    
    if results['energy_metrics']:
        print("\nEnergy Metrics Found:")
        print(json.dumps(results['energy_metrics'], indent=2))
    
    if results['metadata'].get('pages_with_visuals'):
        print(f"\nNote: {len(results['metadata']['pages_with_visuals'])} pages contain charts/images")
        print("These may require manual review or OCR for complete data extraction")


if __name__ == "__main__":
    main()