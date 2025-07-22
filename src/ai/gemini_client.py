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
        
        # Use custom prompt if provided, otherwise use default
        if custom_prompt:
            extraction_prompt = custom_prompt
        else:
            # Default structured prompt for data extraction
            extraction_prompt = """
        Analyze this earnings report page and extract ALL financial data, metrics, and segments.
        
        Focus on finding:
        1. Vehicle Production and Deliveries:
           - Model 3/Y numbers
           - Model S/X numbers
           - Total production
           - Total deliveries
           - By quarter if available
        
        2. Energy Metrics:
           - Energy storage deployed (in GWh)
           - Solar deployed (in MW)
           - Megapack, Powerwall numbers
        
        3. Financial Segments:
           - Automotive revenue
           - Energy generation and storage revenue
           - Services and other revenue
           - Revenue by geography (US, China, Europe, Other)
        
        4. Margins:
           - Total gross margin %
           - Automotive gross margin %
           - Operating margin %
        
        5. Any other key metrics shown in charts, tables, or text
        
        Return the data as a JSON object with this structure:
        {
            "vehicle_metrics": {
                "production": {"Model 3/Y": number, "Model S/X": number, "total": number},
                "deliveries": {"Model 3/Y": number, "Model S/X": number, "total": number}
            },
            "energy_metrics": {
                "storage_deployed_gwh": number,
                "solar_deployed_mw": number
            },
            "financial_segments": {
                "automotive_revenue": number,
                "energy_revenue": number,
                "services_revenue": number,
                "total_revenue": number
            },
            "geographic_revenue": {
                "united_states": number,
                "china": number,
                "europe": number,
                "other": number
            },
            "margins": {
                "total_gross_margin": number,
                "automotive_gross_margin": number,
                "operating_margin": number
            },
            "period": "Q1 2025" or appropriate period,
            "page_number": number
        }
        
        Extract actual numbers from charts, graphs, tables, and text. If a value is shown as a percentage, include the % symbol.
        """
        
        # Add expected structure to prompt if provided
        if expected_structure and not custom_prompt:
            extraction_prompt += f"\n\nExpected data structure:\n{json.dumps(expected_structure, indent=2)}"
        
        all_extracted_data = {
            "vehicle_metrics": {},
            "energy_metrics": {},
            "financial_segments": {},
            "geographic_revenue": {},
            "margins": {},
            "raw_extractions": []
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
                    
                    # Merge data (prefer non-empty values)
                    self._merge_extracted_data(all_extracted_data, extracted)
                    
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
    
    def _merge_extracted_data(self, target: Dict, source: Dict):
        """Merge extracted data, preferring non-empty values"""
        for key in ['vehicle_metrics', 'energy_metrics', 'financial_segments', 'geographic_revenue', 'margins']:
            if key in source and source[key]:
                if not target[key]:
                    target[key] = source[key]
                else:
                    # Merge dictionaries, preferring non-zero values
                    for sub_key, value in source[key].items():
                        if value and (sub_key not in target[key] or not target[key][sub_key]):
                            target[key][sub_key] = value
    
    def _post_process_extraction(self, data: Dict):
        """Clean and validate extracted data"""
        # Add extraction summary
        data['extraction_summary'] = {
            'pages_processed': len(data.get('raw_extractions', [])),
            'vehicle_data_complete': bool(data.get('vehicle_metrics', {}).get('deliveries')),
            'energy_data_complete': bool(data.get('energy_metrics', {}).get('storage_deployed_gwh')),
            'financial_segments_complete': bool(data.get('financial_segments', {}).get('automotive_revenue')),
            'geographic_data_complete': bool(data.get('geographic_revenue')),
            'margins_complete': bool(data.get('margins', {}).get('total_gross_margin'))
        }
        
        # Calculate completeness score
        completeness = sum(1 for v in data['extraction_summary'].values() if v and isinstance(v, bool))
        data['extraction_summary']['completeness_score'] = completeness / 5 * 100
        
        logger.info(f"Extraction completeness: {data['extraction_summary']['completeness_score']}%")
    
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