"""
Optimized PDF Extractor - Batch processing with smart page selection
"""
import logging
from typing import Dict, List, Any, Optional, Set
import time
from pathlib import Path
import hashlib
import json
import re
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


class OptimizedPDFExtractor:
    """
    Optimized extraction that processes only required pages in small batches
    """
    
    def __init__(self, gemini_client, cache_dir: str = "output/cache"):
        self.gemini_client = gemini_client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.batch_size = 3  # Process 3 pages at a time
        self.delay_between_batches = 5  # 5 seconds between batches
        self.delay_between_pages = 2  # 2 seconds between pages in batch
        
    def extract_specific_pages(self, pdf_path: str, page_groups: List[Dict[str, Any]], 
                              custom_prompts: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Extract data from specific page groups efficiently
        
        Args:
            pdf_path: Path to PDF file
            page_groups: List of dicts with 'data_type' and 'pages' keys
            custom_prompts: Optional dict mapping data_type to custom prompts
            
        Returns:
            Extracted data organized by data type
        """
        start_time = time.time()
        logger.info(f"Starting optimized extraction for: {pdf_path}")
        
        # Collect all unique pages needed
        all_pages = set()
        page_to_types = {}  # Map page to data types
        
        for group in page_groups:
            data_type = group['data_type']
            pages = group['pages']
            for page in pages:
                all_pages.add(page)
                if page not in page_to_types:
                    page_to_types[page] = []
                page_to_types[page].append(data_type)
        
        logger.info(f"Need to process {len(all_pages)} unique pages: {sorted(all_pages)}")
        
        # Convert only needed pages to images
        pdf_images = self._convert_specific_pages(pdf_path, sorted(all_pages))
        
        # Initialize results
        results = {
            "data_by_type": {},
            "raw_extractions": [],
            "extracted_values": [],
            "extraction_summary": {
                "pages_requested": len(all_pages),
                "pages_processed": 0,
                "cache_hits": 0,
                "extraction_time": 0,
                "errors": []
            }
        }
        
        # Process pages in batches
        pages_list = sorted(all_pages)
        for i in range(0, len(pages_list), self.batch_size):
            batch_pages = pages_list[i:i + self.batch_size]
            logger.info(f"Processing batch: pages {batch_pages}")
            
            for page_num in batch_pages:
                # Check cache first
                cache_key = self._get_cache_key(pdf_path, page_num)
                cached_result = self._get_cached_result(cache_key)
                
                if cached_result:
                    logger.info(f"Cache hit for page {page_num}")
                    results["extraction_summary"]["cache_hits"] += 1
                    self._process_cached_result(results, cached_result, page_num, page_to_types[page_num])
                else:
                    # Extract from page
                    try:
                        # Get appropriate prompt for this page
                        data_types = page_to_types[page_num]
                        prompt = self._get_combined_prompt(data_types, custom_prompts)
                        
                        # Extract data
                        extracted = self._extract_from_page(
                            pdf_images[page_num], 
                            page_num, 
                            prompt
                        )
                        
                        if extracted:
                            # Cache the result
                            self._cache_result(cache_key, extracted)
                            
                            # Process and organize by data type
                            self._organize_extracted_data(results, extracted, page_num, data_types)
                            results["extraction_summary"]["pages_processed"] += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing page {page_num}: {e}")
                        results["extraction_summary"]["errors"].append({
                            "page": page_num,
                            "error": str(e)
                        })
                
                # Delay between pages in batch
                if page_num != batch_pages[-1]:
                    time.sleep(self.delay_between_pages)
            
            # Delay between batches
            if i + self.batch_size < len(pages_list):
                logger.info(f"Waiting {self.delay_between_batches}s before next batch...")
                time.sleep(self.delay_between_batches)
        
        # Summary
        results["extraction_summary"]["extraction_time"] = time.time() - start_time
        logger.info(f"Extraction completed in {results['extraction_summary']['extraction_time']:.1f}s")
        
        return results
    
    def _convert_specific_pages(self, pdf_path: str, pages: List[int]) -> Dict[int, Any]:
        """Convert only specific pages to images"""
        logger.info(f"Converting pages {pages} to images...")
        
        # pdf2image uses 1-based indexing
        pdf_images = convert_from_path(
            pdf_path, 
            dpi=150,
            first_page=min(pages),
            last_page=max(pages)
        )
        
        # Create mapping
        image_dict = {}
        offset = min(pages) - 1
        for i, page_num in enumerate(range(min(pages), max(pages) + 1)):
            if page_num in pages:
                image_dict[page_num] = pdf_images[i]
        
        return image_dict
    
    def _extract_from_page(self, image: Any, page_num: int, prompt: str) -> Dict:
        """Extract data from a single page"""
        logger.info(f"Extracting from page {page_num}")
        
        try:
            response = self.gemini_client.vision_model.generate_content([prompt, image])
            
            # Parse response
            extracted = self._parse_json_response(response.text)
            
            if extracted:
                extracted['page_number'] = page_num
                return extracted
            else:
                # If JSON parsing fails, try to extract key-value pairs
                return self._extract_fallback(response.text, page_num)
                
        except Exception as e:
            logger.error(f"Extraction failed for page {page_num}: {e}")
            raise
    
    def _parse_json_response(self, response_text: str) -> Optional[Dict]:
        """Parse JSON from response text"""
        # Try to find JSON in the response
        
        # Look for JSON structure
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try parsing the whole response
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return None
    
    def _extract_fallback(self, text: str, page_num: int) -> Dict:
        """Fallback extraction using pattern matching"""
        extracted = {"page_number": page_num, "raw_text": text[:1000]}
        
        # Extract numbers with labels
        import re
        patterns = {
            'revenue': r'(?:revenue|sales).*?(\$?[\d,]+\.?\d*[MB]?)',
            'margin': r'(?:margin).*?([\d.]+%)',
            'production': r'(?:production|produced).*?([\d,]+)',
            'deliveries': r'(?:deliver(?:y|ies|ed)).*?([\d,]+)'
        }
        
        for key, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                extracted[key] = matches[0]
        
        return extracted
    
    def _get_combined_prompt(self, data_types: List[str], custom_prompts: Dict[str, str] = None) -> str:
        """Create a combined prompt for multiple data types"""
        if custom_prompts and len(data_types) == 1 and data_types[0] in custom_prompts:
            return custom_prompts[data_types[0]]
        
        # Default prompt
        return f"""Extract financial and operational data from this page. 
        Focus on: {', '.join(data_types)}
        
        Return data in JSON format with clear structure. Include:
        - All numerical values with their labels
        - Revenue breakdowns by segment
        - Operational metrics (production, deliveries)
        - Margins and profitability metrics
        - Any time series data
        
        Format numbers clearly and include units (M for millions, B for billions, % for percentages)."""
    
    def _organize_extracted_data(self, results: Dict, extracted: Dict, page_num: int, data_types: List[str]):
        """Organize extracted data by type"""
        # Add to raw extractions
        results["raw_extractions"].append(extracted)
        
        # Organize by data type
        for data_type in data_types:
            if data_type not in results["data_by_type"]:
                results["data_by_type"][data_type] = {}
            
            # Store relevant data for this type
            if data_type == "financial":
                # Look for financial data in various forms
                if "FinancialSummary" in extracted:
                    fin_data = extracted["FinancialSummary"]
                    if "Revenue" in fin_data and "Total" in fin_data["Revenue"]:
                        # Get the latest quarter value (Q1-2025)
                        total_values = fin_data["Revenue"]["Total"]
                        if len(total_values) >= 5:  # Q1-2025 is at index 4
                            results["data_by_type"][data_type]["revenue"] = total_values[4]
                        
                        # Also extract segments
                        if "TotalAutomotive" in fin_data["Revenue"]:
                            results["data_by_type"][data_type]["automotive_revenue"] = fin_data["Revenue"]["TotalAutomotive"][4]
                        if "EnergyGenerationAndStorage" in fin_data["Revenue"]:
                            results["data_by_type"][data_type]["energy_revenue"] = fin_data["Revenue"]["EnergyGenerationAndStorage"][4]
                        if "ServicesAndOther" in fin_data["Revenue"]:
                            results["data_by_type"][data_type]["services_revenue"] = fin_data["Revenue"]["ServicesAndOther"][4]
                            
                elif "revenue" in str(extracted).lower():
                    # Fallback pattern matching
                    revenue_match = re.search(r'(?:total.*?revenue|revenue.*?total).*?(\$?[\d,]+\.?\d*[MB]?)', 
                                            str(extracted), re.IGNORECASE)
                    if revenue_match:
                        results["data_by_type"][data_type]["revenue"] = revenue_match.group(1)
                        
            elif data_type == "operational_metrics":
                # Look for operational data
                if "operational_summary" in extracted:
                    ops_data = extracted["operational_summary"]
                    # Look for time series data
                    if "time_series_data" in ops_data:
                        for series in ops_data["time_series_data"]:
                            metric = series.get("metric", "").lower()
                            if "total production" in metric and "Q1-2025" in series:
                                results["data_by_type"][data_type]["production"] = series["Q1-2025"]
                            elif "total deliveries" in metric and "Q1-2025" in series:
                                results["data_by_type"][data_type]["deliveries"] = series["Q1-2025"]
                else:
                    # Fallback pattern matching
                    for key in ["production", "deliveries", "vehicle_deliveries"]:
                        pattern = rf'{key}.*?([\d,]+)'
                        match = re.search(pattern, str(extracted), re.IGNORECASE)
                        if match:
                            results["data_by_type"][data_type][key] = match.group(1)
                            
            elif data_type == "segment_metrics":
                # Look for energy/segment specific metrics
                if "energy" in str(extracted).lower():
                    # Extract energy metrics
                    energy_pattern = r'energy.*?storage.*?([\d,]+)'
                    match = re.search(energy_pattern, str(extracted), re.IGNORECASE)
                    if match:
                        results["data_by_type"][data_type]["energy_storage"] = match.group(1)
                        
            # Add extracted values to the list
            self._extract_values_to_list(results, extracted, page_num, data_type)
    
    def _extract_values_to_list(self, results: Dict, extracted: Dict, page_num: int, data_type: str):
        """Extract individual values to the extracted_values list"""
        # This method extracts normalized values for generic processing
        def extract_from_dict(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if isinstance(value, (str, int, float)) and not key.lower() in ['units', 'timeperiod']:
                        # Try to identify the value type
                        value_type = "other"
                        if "revenue" in new_path.lower():
                            value_type = "revenue"
                        elif "margin" in new_path.lower():
                            value_type = "margin"
                        elif any(term in new_path.lower() for term in ["production", "delivery", "deliveries"]):
                            value_type = "operational"
                        
                        results["extracted_values"].append({
                            "path": new_path,
                            "key": key,
                            "value": value,
                            "page": page_num,
                            "type": value_type,
                            "data_type": data_type
                        })
                    elif isinstance(value, (dict, list)):
                        extract_from_dict(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_from_dict(item, f"{path}[{i}]")
        
        extract_from_dict(extracted)
    
    def _process_cached_result(self, results: Dict, cached: Dict, page_num: int, data_types: List[str]):
        """Process a cached result"""
        self._organize_extracted_data(results, cached, page_num, data_types)
        results["extraction_summary"]["pages_processed"] += 1
    
    def _get_cache_key(self, pdf_path: str, page_num: int) -> str:
        """Generate cache key for a page"""
        pdf_name = Path(pdf_path).stem
        return f"{pdf_name}_page_{page_num}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached result if available"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def _cache_result(self, cache_key: str, result: Dict):
        """Cache extraction result"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")