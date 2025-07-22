"""
Parallel PDF Extractor - High-performance concurrent page processing
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from pathlib import Path
import hashlib
import json
import os

logger = logging.getLogger(__name__)


class ParallelPDFExtractor:
    """
    Extracts data from PDF pages in parallel using multiple workers
    Includes caching, progress tracking, and intelligent page selection
    """
    
    def __init__(self, gemini_client, max_workers: int = 1, cache_dir: str = "output/cache"):
        self.gemini_client = gemini_client
        self.max_workers = max_workers  # Set to 1 to avoid rate limits
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.request_times = []  # Track request times for rate limiting
        self.requests_per_minute = 8  # Conservative limit below Gemini's 10/min
        self.retry_count = 3  # Number of retries for failed requests
        self.base_delay = 2.0  # Base delay between requests in seconds
        
    def extract_parallel(self, pdf_path: str, page_priorities: Dict[int, float] = None,
                        custom_prompt: str = None, expected_structure: Dict = None) -> Dict[str, Any]:
        """
        Extract data from PDF using parallel processing
        
        Args:
            pdf_path: Path to PDF file
            page_priorities: Dict mapping page numbers to priority scores (0-1)
            custom_prompt: Optional custom extraction prompt
            expected_structure: Optional expected data structure
            
        Returns:
            Extracted data from all pages
        """
        start_time = time.time()
        logger.info(f"Starting parallel extraction for: {pdf_path}")
        
        # Convert PDF to images
        pdf_images = self._pdf_to_images_with_priority(pdf_path, page_priorities)
        total_pages = len(pdf_images)
        
        # Initialize results
        all_extracted_data = {
            "raw_extractions": [],
            "extracted_values": [],
            "extraction_metadata": {
                "total_pages": total_pages,
                "pages_processed": 0,
                "extraction_time": 0,
                "cache_hits": 0,
                "errors": []
            }
        }
        
        # Process pages in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all pages for processing
            future_to_page = {}
            for page_num, image, priority in pdf_images:
                # Check cache first
                cache_key = self._get_cache_key(pdf_path, page_num, custom_prompt)
                cached_result = self._get_cached_result(cache_key)
                
                if cached_result:
                    logger.info(f"Cache hit for page {page_num}")
                    all_extracted_data["extraction_metadata"]["cache_hits"] += 1
                    self._merge_page_results(all_extracted_data, cached_result, page_num)
                else:
                    # Submit for processing
                    future = executor.submit(
                        self._process_single_page,
                        page_num, image, custom_prompt, expected_structure
                    )
                    future_to_page[future] = (page_num, cache_key)
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_page):
                page_num, cache_key = future_to_page[future]
                completed += 1
                
                try:
                    result = future.result(timeout=30)  # 30 second timeout per page
                    if result:
                        # Cache the result
                        self._cache_result(cache_key, result)
                        # Merge into main results
                        self._merge_page_results(all_extracted_data, result, page_num)
                        
                    logger.info(f"Processed page {page_num} ({completed}/{len(future_to_page)} pages)")
                    
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {e}")
                    all_extracted_data["extraction_metadata"]["errors"].append({
                        "page": page_num,
                        "error": str(e)
                    })
        
        # Update metadata
        all_extracted_data["extraction_metadata"]["pages_processed"] = completed
        all_extracted_data["extraction_metadata"]["extraction_time"] = time.time() - start_time
        
        logger.info(f"Parallel extraction complete in {all_extracted_data['extraction_metadata']['extraction_time']:.2f} seconds")
        logger.info(f"Processed {completed} pages with {all_extracted_data['extraction_metadata']['cache_hits']} cache hits")
        
        return all_extracted_data
    
    def _pdf_to_images_with_priority(self, pdf_path: str, 
                                    page_priorities: Dict[int, float] = None) -> List[Tuple[int, Any, float]]:
        """
        Convert PDF to images and sort by priority
        Returns list of (page_num, image, priority) tuples
        """
        from pdf2image import convert_from_path
        
        # Convert all pages
        pdf_images = convert_from_path(pdf_path, dpi=150)
        total_pages = len(pdf_images)
        
        # Create page list with priorities
        pages_with_priority = []
        
        for page_num in range(1, total_pages + 1):
            # Default priority based on page position
            if page_priorities and page_num in page_priorities:
                priority = page_priorities[page_num]
            else:
                # Higher priority for pages with financial data (usually pages 3-6)
                if page_num in [4, 5]:  # Key financial summary pages
                    priority = 1.0
                elif page_num in [3, 6, 7]:
                    priority = 0.9
                elif page_num <= 10:
                    priority = 0.7
                elif page_num <= 20:
                    priority = 0.5
                else:
                    priority = 0.3
            
            pages_with_priority.append((page_num, pdf_images[page_num - 1], priority))
        
        # Sort by priority (highest first)
        pages_with_priority.sort(key=lambda x: x[2], reverse=True)
        
        # For now, process top 15 pages max to avoid timeout
        return pages_with_priority[:15]
    
    def _process_single_page(self, page_num: int, image: Any, 
                           custom_prompt: str = None, expected_structure: Dict = None) -> Dict:
        """Process a single page with retry logic"""
        for retry in range(self.retry_count + 1):
            try:
                logger.debug(f"Processing page {page_num} (attempt {retry + 1}/{self.retry_count + 1})")
                
                # Apply rate limiting with exponential backoff
                self._apply_rate_limit(retry_count=retry)
                
                # Use the gemini client's vision model directly
                prompt = custom_prompt or self._get_default_prompt()
                
                # Add page context to prompt
                contextualized_prompt = f"{prompt}\n\nYou are looking at page {page_num} of an earnings report."
                
                response = self.gemini_client.vision_model.generate_content([contextualized_prompt, image])
                
                # Parse response
                extracted = self._parse_json_response(response.text)
                
                if extracted:
                    extracted['page_number'] = page_num
                    logger.info(f"Successfully extracted data from page {page_num}")
                    return {
                        "page": page_num,
                        "extracted_data": extracted,
                        "success": True
                    }
                else:
                    raise ValueError("Failed to parse JSON response")
                    
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a rate limit error
                if "429" in error_msg or "quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                    logger.warning(f"Rate limit hit on page {page_num}, retry {retry + 1}/{self.retry_count + 1}")
                    if retry < self.retry_count:
                        # Extra wait for rate limit errors
                        time.sleep(5)
                        continue
                
                # Log error and potentially retry
                if retry < self.retry_count:
                    logger.warning(f"Error on page {page_num} (retry {retry + 1}): {error_msg}")
                    continue
                else:
                    logger.error(f"Failed to process page {page_num} after {self.retry_count + 1} attempts: {error_msg}")
                    return {
                        "page": page_num,
                        "extracted_data": {},
                        "success": False,
                        "error": error_msg
                    }
    
    def _get_default_prompt(self) -> str:
        """Get default extraction prompt"""
        return """
        Extract ALL financial and operational data from this earnings report page.
        
        Return a JSON object with this exact structure (fill in values you find):
        {
            "revenue": {
                "total": "value with unit (e.g., 19335M)",
                "automotive": "value with unit",
                "energy": "value with unit",
                "services": "value with unit",
                "other_segments": {"segment_name": "value"}
            },
            "margins": {
                "gross_margin": "percentage (e.g., 16.3%)",
                "operating_margin": "percentage",
                "net_margin": "percentage"
            },
            "income": {
                "gross_profit": "value with unit",
                "operating_income": "value with unit",
                "net_income": "value with unit"
            },
            "operational": {
                "deliveries": "number",
                "production": "number",
                "capacity": "number",
                "other_metrics": {"metric_name": "value"}
            },
            "costs": {
                "cost_of_revenue": "value with unit",
                "operating_expenses": "value with unit",
                "r_and_d": "value with unit"
            },
            "period": "Q1 2025 or similar",
            "comparisons": {
                "yoy_revenue_growth": "percentage",
                "qoq_revenue_growth": "percentage"
            }
        }
        
        IMPORTANT:
        1. Include the exact values as shown (e.g., "$19,335M" or "19335M")
        2. Keep percentages with % symbol (e.g., "16.3%")
        3. For missing values, omit the key rather than using null
        4. Extract ALL numbers you see with their context
        """
    
    def _parse_json_response(self, response_text: str) -> Optional[Dict]:
        """Extract JSON from response text"""
        try:
            # Log response for debugging
            logger.debug(f"Response text length: {len(response_text)}")
            
            # Remove markdown code block markers if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]  # Remove ```json
            if cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:]  # Remove ```
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]  # Remove trailing ```
            
            cleaned_text = cleaned_text.strip()
            
            # Try to parse the cleaned text first
            try:
                parsed = json.loads(cleaned_text)
                logger.debug(f"Successfully parsed JSON with {len(parsed)} keys")
                return parsed
            except json.JSONDecodeError:
                pass
            
            # Find JSON in response as fallback
            json_start = cleaned_text.find('{')
            json_end = cleaned_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_text[json_start:json_end]
                parsed = json.loads(json_str)
                logger.debug(f"Successfully parsed JSON with {len(parsed)} keys")
                return parsed
            else:
                logger.warning(f"No JSON structure found. Response preview: {response_text[:100]}...")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error at position {e.pos}: {e.msg}")
            logger.debug(f"Failed to parse: {cleaned_text[:200]}...")
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {type(e).__name__}: {e}")
            
        return None
    
    def _merge_page_results(self, all_data: Dict, page_result: Dict, page_num: int):
        """Merge results from a single page into the main data structure"""
        if page_result.get("success") and page_result.get("extracted_data"):
            extracted = page_result["extracted_data"]
            
            # Add to raw extractions
            all_data["raw_extractions"].append(extracted)
            
            # Extract values generically
            self._extract_values_from_dict(extracted, all_data["extracted_values"], page_num)
    
    def _extract_values_from_dict(self, data: Dict, values_list: List, page_num: int, path: str = ""):
        """Recursively extract all values from a dictionary"""
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, dict):
                self._extract_values_from_dict(value, values_list, page_num, current_path)
            elif isinstance(value, (int, float, str)) and key != "page_number":
                values_list.append({
                    "path": current_path,
                    "key": key,
                    "value": value,
                    "page": page_num,
                    "type": self._infer_value_type(current_path, value)
                })
    
    def _infer_value_type(self, path: str, value: Any) -> str:
        """Infer the type of value from its path"""
        path_lower = path.lower()
        
        if any(term in path_lower for term in ['revenue', 'sales']):
            return 'revenue'
        elif any(term in path_lower for term in ['margin', 'gross', 'operating']):
            return 'margin'
        elif any(term in path_lower for term in ['income', 'profit', 'earnings']):
            return 'income'
        elif isinstance(value, str) and '%' in str(value):
            return 'percentage'
        else:
            return 'other'
    
    def _get_cache_key(self, pdf_path: str, page_num: int, prompt: str = None) -> str:
        """Generate cache key for a page"""
        # Create hash from pdf path, page number, and prompt
        key_string = f"{pdf_path}:{page_num}:{prompt or 'default'}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached result if exists"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                
        return None
    
    def _cache_result(self, cache_key: str, result: Dict):
        """Cache extraction result"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
    
    def _apply_rate_limit(self, retry_count: int = 0):
        """Apply rate limiting with exponential backoff"""
        import threading
        
        with threading.Lock():
            current_time = time.time()
            
            # Apply exponential backoff for retries
            if retry_count > 0:
                backoff_time = self.base_delay * (2 ** (retry_count - 1))
                logger.info(f"Retry {retry_count}: Applying exponential backoff of {backoff_time:.1f}s")
                time.sleep(backoff_time)
            
            # Remove old request times (older than 60 seconds)
            self.request_times = [t for t in self.request_times if current_time - t < 60]
            
            # If we've made too many requests, wait
            if len(self.request_times) >= self.requests_per_minute:
                oldest_request = min(self.request_times)
                wait_time = 60 - (current_time - oldest_request) + 2  # Extra 2s buffer
                
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
            else:
                # Apply base delay between requests
                time.sleep(self.base_delay)
                    
            # Record this request
            self.request_times.append(time.time())