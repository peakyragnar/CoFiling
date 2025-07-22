"""Gemini AI client for PDF parsing and financial model generation"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from pathlib import Path
import PIL.Image
import io
import pypdf
from .parallel_extractor import ParallelPDFExtractor

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, will use system environment variables
    pass

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Google Gemini AI API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client
        
        Args:
            api_key: Google AI API key (uses GOOGLE_API_KEY env var if not provided)
        """
        self.api_key = api_key or os.environ.get('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key required. Set GOOGLE_API_KEY environment variable.")
        
        genai.configure(api_key=self.api_key)
        
        # Initialize model for multimodal analysis
        self.vision_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Model for structured output
        self.pro_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        logger.info("Gemini client initialized")
        
        # Initialize parallel extractor with fewer workers to avoid rate limits
        self.parallel_extractor = ParallelPDFExtractor(self, max_workers=2)
    
    def extract_pdf_data_parallel(self, pdf_path: str, page_priorities: Optional[Dict[int, float]] = None,
                                 custom_prompt: Optional[str] = None, expected_structure: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract data from PDF using parallel processing for better performance
        
        Args:
            pdf_path: Path to PDF file
            page_priorities: Optional dict mapping page numbers to priority scores
            custom_prompt: Optional custom extraction prompt
            expected_structure: Optional expected data structure
            
        Returns:
            Extracted data with parallel processing metadata
        """
        logger.info(f"Starting parallel extraction for: {pdf_path}")
        
        # Use parallel extractor
        result = self.parallel_extractor.extract_parallel(
            pdf_path, 
            page_priorities=page_priorities,
            custom_prompt=custom_prompt,
            expected_structure=expected_structure
        )
        
        # Post-process the results
        self._post_process_extraction(result)
        
        return result
    
    def extract_pdf_data(self, pdf_path: str, page_numbers: Optional[List[int]] = None, 
                        custom_prompt: Optional[str] = None, expected_structure: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract structured data from PDF using Gemini's vision capabilities
        
        Args:
            pdf_path: Path to PDF file
            page_numbers: Specific pages to analyze (None = all pages)
            custom_prompt: Optional custom prompt for extraction
            expected_structure: Optional structure to guide extraction
            
        Returns:
            Extracted data including segments, metrics, and financial data
        """
        logger.info(f"Extracting data from PDF: {pdf_path}")
        
        # Convert PDF pages to images
        pdf_images = self._pdf_to_images(pdf_path, page_numbers)
        
        # Use custom prompt if provided, otherwise use generic prompt
        if custom_prompt:
            extraction_prompt = custom_prompt
        else:
            # Generic structured prompt for data extraction
            extraction_prompt = """
        Analyze this earnings report page and extract ALL financial data, metrics, and segments.
        
        Extract any data you find including but not limited to:
        1. Revenue data (total, by segment, by geography)
        2. Operational metrics (units, volumes, customers, etc.)
        3. Financial metrics (margins, profits, costs)
        4. Time series data (quarterly/yearly comparisons)
        5. Any other key metrics shown in charts, tables, or text
        
        Return the data as a JSON object. Include:
        - The actual values found
        - Units (millions, billions, %, etc.)
        - The context/label for each value
        - Period information if available
        
        Focus on extracting concrete numbers and their contexts.
        """
        
        # Add expected structure to prompt if provided
        if expected_structure:
            extraction_prompt += f"\n\nExpected data structure:\n{json.dumps(expected_structure, indent=2)}"
        
        # Initialize generic data structure
        all_extracted_data = {
            "raw_extractions": [],
            "extracted_values": []  # Store all extracted values generically
        }
        
        # Process each page
        for page_num, image in pdf_images:
            try:
                logger.info(f"Processing page {page_num} with Gemini")
                
                # Generate content with vision model
                response = self.vision_model.generate_content([extraction_prompt, image])
                
                # Parse JSON from response
                extracted = self._parse_json_response(response.text)
                
                if extracted:
                    extracted['page_number'] = page_num
                    all_extracted_data['raw_extractions'].append(extracted)
                    
                    # Store all extracted values generically
                    self._extract_generic_values(all_extracted_data, extracted, page_num)
                    
            except Exception as e:
                logger.error(f"Error processing page {page_num}: {e}")
                continue
        
        # Post-process to clean and validate
        self._post_process_extraction(all_extracted_data)
        
        return all_extracted_data
    
    def _pdf_to_images(self, pdf_path: str, page_numbers: Optional[List[int]] = None) -> List[tuple]:
        """Convert PDF pages to PIL images for Gemini processing"""
        from pdf2image import convert_from_path
        
        images = []
        
        # Convert PDF to images
        try:
            # Convert all pages to images
            pdf_images = convert_from_path(pdf_path, dpi=150)
            total_pages = len(pdf_images)
            
            # Determine which pages to process
            if page_numbers:
                pages_to_process = [p for p in page_numbers if 0 < p <= total_pages]
            else:
                # For efficiency, focus on key pages (typically first 15 pages have key data)
                pages_to_process = list(range(1, min(16, total_pages + 1)))
            
            logger.info(f"Processing {len(pages_to_process)} pages from PDF")
            
            # Get the specific pages
            for page_num in pages_to_process:
                # Page numbers are 1-based, but list is 0-based
                image = pdf_images[page_num - 1]
                images.append((page_num, image))
                
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            logger.info("Ensure poppler-utils is installed: brew install poppler (macOS) or apt-get install poppler-utils (Linux)")
            raise
        
        return images
    
    def _parse_json_response(self, response_text: str) -> Optional[Dict]:
        """Extract JSON from Gemini response"""
        try:
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                logger.warning("No JSON found in response")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
    
    def _extract_generic_values(self, target: Dict, source: Dict, page_num: int):
        """Extract values generically from the response"""
        def extract_values(obj, path=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if isinstance(value, (int, float, str)) and value:
                        # It's a value
                        target['extracted_values'].append({
                            'path': new_path,
                            'key': key,
                            'value': value,
                            'page': page_num,
                            'type': self._infer_value_type(new_path, value)
                        })
                    else:
                        # Recurse
                        extract_values(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_values(item, f"{path}[{i}]")
        
        extract_values(source)
    
    def _infer_value_type(self, path: str, value: Any) -> str:
        """Infer the type of value from its path and content"""
        path_lower = path.lower()
        
        if any(term in path_lower for term in ['revenue', 'sales']):
            return 'revenue'
        elif any(term in path_lower for term in ['margin', 'gross', 'operating']):
            return 'margin'
        elif any(term in path_lower for term in ['production', 'delivery', 'units', 'volume']):
            return 'operational'
        elif any(term in path_lower for term in ['income', 'profit', 'earnings']):
            return 'income'
        elif isinstance(value, str) and '%' in str(value):
            return 'percentage'
        else:
            return 'other'
    
    def _post_process_extraction(self, data: Dict):
        """Clean and validate extracted data"""
        # Add extraction summary
        data['extraction_summary'] = {
            'pages_processed': len(data.get('raw_extractions', [])),
            'total_values_extracted': len(data.get('extracted_values', [])),
            'value_types': {}
        }
        
        # Count values by type
        for value_info in data.get('extracted_values', []):
            value_type = value_info.get('type', 'other')
            data['extraction_summary']['value_types'][value_type] = \
                data['extraction_summary']['value_types'].get(value_type, 0) + 1
        
        logger.info(f"Extracted {data['extraction_summary']['total_values_extracted']} values")
    
    def generate_financial_model(self, sec_data: Dict, earnings_data: Dict) -> Dict[str, Any]:
        """
        Generate financial model using merged SEC and earnings data
        
        Args:
            sec_data: Structured SEC filing data
            earnings_data: Extracted earnings report data
            
        Returns:
            Complete financial model with projections
        """
        # This will be implemented in Phase 2
        # For now, return a placeholder
        return {
            "status": "not_implemented",
            "message": "Financial model generation will be implemented in Phase 2"
        }


class GeminiPDFParser:
    """Enhanced PDF parser using Gemini for complete data extraction"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.gemini_client = GeminiClient(api_key)
        self.logger = logging.getLogger(__name__)
    
    def parse_earnings_pdf(self, pdf_path: str, use_gemini: bool = True) -> Dict[str, Any]:
        """
        Parse earnings PDF with optional Gemini enhancement
        
        Args:
            pdf_path: Path to PDF file
            use_gemini: Whether to use Gemini for visual extraction
            
        Returns:
            Complete extracted data
        """
        from extraction.earnings_parser import EarningsParser
        
        # First, use traditional parser for tables
        traditional_parser = EarningsParser()
        base_data = traditional_parser.parse_earnings_pdf(pdf_path)
        
        if use_gemini:
            # Enhance with Gemini for visual data
            self.logger.info("Enhancing extraction with Gemini Vision")
            
            # Focus on pages with missing data
            target_pages = self._identify_target_pages(base_data)
            
            # Extract using Gemini
            gemini_data = self.gemini_client.extract_pdf_data(pdf_path, target_pages)
            
            # Merge results
            self._merge_results(base_data, gemini_data)
        
        return base_data
    
    def _identify_target_pages(self, base_data: Dict) -> List[int]:
        """Identify pages that likely contain missing data"""
        target_pages = []
        
        # Check what's missing
        if not base_data.get('energy_metrics', {}).get('storage_deployed_gwh'):
            target_pages.extend([9, 10, 11])  # Energy section usually here
        
        if not base_data.get('financial_segments'):
            target_pages.extend([4, 5, 23, 24])  # Financial summary pages
        
        if not base_data.get('geographic_segments'):
            target_pages.extend([25, 26, 27])  # Geographic data often later
        
        # Always check key summary pages
        target_pages.extend([1, 2, 3, 6])
        
        # Remove duplicates and sort
        return sorted(list(set(target_pages)))
    
    def _merge_results(self, base_data: Dict, gemini_data: Dict):
        """Merge Gemini results into base data"""
        # Update with Gemini findings
        for key in ['vehicle_metrics', 'energy_metrics', 'financial_segments', 'geographic_revenue', 'margins']:
            if key in gemini_data and gemini_data[key]:
                if key not in base_data:
                    base_data[key] = {}
                
                # Merge, preferring Gemini data for missing values
                for sub_key, value in gemini_data[key].items():
                    if value and (sub_key not in base_data[key] or not base_data[key].get(sub_key)):
                        base_data[key][sub_key] = value
                        self.logger.info(f"Added {key}.{sub_key} from Gemini: {value}")
        
        # Update extraction summary
        if 'extraction_summary' not in base_data:
            base_data['extraction_summary'] = {}
        
        base_data['extraction_summary']['gemini_enhanced'] = True
        base_data['extraction_summary']['gemini_pages_processed'] = len(gemini_data.get('raw_extractions', []))