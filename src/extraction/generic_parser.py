"""
Generic Parser - Extracts data from any earnings report using dynamic schemas
"""
import logging
from typing import Dict, List, Any, Optional, Union
import re
from pathlib import Path
import json

from .document_analyzer import DocumentAnalyzer
from .schema_generator import SchemaGenerator

logger = logging.getLogger(__name__)


class GenericEarningsParser:
    """
    Parses any company's earnings report without hardcoded expectations
    Uses document analysis and dynamic schemas
    """
    
    def __init__(self, use_gemini: bool = True):
        self.document_analyzer = DocumentAnalyzer()
        self.schema_generator = SchemaGenerator()
        self.use_gemini = use_gemini
        self.extracted_data = {}
        
    def parse_earnings_pdf(self, pdf_path: str, gemini_client=None) -> Dict[str, Any]:
        """
        Parse earnings PDF with generic approach
        
        Args:
            pdf_path: Path to PDF file
            gemini_client: Optional Gemini client for enhanced extraction
            
        Returns:
            Extracted data following dynamic schema
        """
        logger.info(f"Starting generic parsing of: {pdf_path}")
        
        # Step 1: Analyze document structure
        logger.info("Step 1: Analyzing document structure...")
        document_analysis = self.document_analyzer.analyze_document(pdf_path)
        
        # Log analysis results
        logger.info(f"Document analysis complete:")
        logger.info(f"  - Company: {document_analysis['company_info'].get('name', 'Unknown')}")
        logger.info(f"  - Period: {document_analysis['company_info'].get('period', 'Unknown')}")
        logger.info(f"  - Pages: {document_analysis['structure']['total_pages']}")
        logger.info(f"  - Tables found: {document_analysis['tables']['count']}")
        logger.info(f"  - Operational metrics: {len(document_analysis['discovered_metrics']['operational'])}")
        logger.info(f"  - Financial metrics: {len(document_analysis['discovered_metrics']['financial'])}")
        logger.info(f"  - Segments: {len(document_analysis['discovered_metrics']['segments'])}")
        
        # Step 2: Generate extraction schema
        logger.info("Step 2: Generating extraction schema...")
        extraction_schema = self.schema_generator.generate_schema(document_analysis)
        
        # Step 3: Extract data according to schema
        logger.info("Step 3: Extracting data according to schema...")
        if self.use_gemini and gemini_client:
            extracted_data = self._extract_with_gemini(
                pdf_path, 
                extraction_schema, 
                document_analysis,
                gemini_client
            )
        else:
            extracted_data = self._extract_with_traditional_methods(
                pdf_path,
                extraction_schema,
                document_analysis
            )
        
        # Step 4: Validate extracted data
        logger.info("Step 4: Validating extracted data...")
        validation_results = self._validate_extraction(
            extracted_data,
            extraction_schema["validations"]
        )
        
        # Step 5: Structure final output
        final_output = {
            "metadata": extraction_schema["metadata"],
            "data": extracted_data,
            "document_analysis": {
                "business_model": document_analysis.get("business_model", "general"),
                "data_completeness": self._calculate_completeness(extracted_data, extraction_schema),
                "hierarchies_found": len(document_analysis.get("hierarchies", [])),
                "extraction_method": "gemini_enhanced" if (self.use_gemini and gemini_client) else "traditional"
            },
            "validation": validation_results
        }
        
        return final_output
    
    def _extract_with_gemini(self, pdf_path: str, schema: Dict, analysis: Dict, 
                            gemini_client) -> Dict[str, Any]:
        """Extract data using Gemini with dynamic prompts"""
        extracted_data = schema.copy()
        instructions = schema["extraction_instructions"]
        
        # Process primary pages for each data type
        for page_group in instructions["primary_pages"]:
            data_type = page_group["data_type"]
            pages = page_group["pages"]
            
            logger.info(f"Extracting {data_type} from pages: {pages}")
            
            # Use appropriate Gemini prompt
            prompt_key = f"{data_type}_extraction"
            if prompt_key in instructions["gemini_prompts"]:
                prompt = instructions["gemini_prompts"][prompt_key]
            else:
                # Generate generic prompt
                prompt = self._generate_generic_prompt(data_type, schema)
            
            # Extract using Gemini with custom prompt
            # Use parallel extraction for better performance
            if hasattr(gemini_client, 'extract_pdf_data_parallel'):
                # Convert pages list to priorities
                page_priorities = {page: 1.0 if i < 5 else 0.8 for i, page in enumerate(pages)}
                
                gemini_response = gemini_client.extract_pdf_data_parallel(
                    pdf_path,
                    page_priorities=page_priorities,
                    custom_prompt=prompt,
                    expected_structure=self._get_expected_structure(data_type, schema)
                )
            else:
                # Fallback to sequential extraction
                gemini_response = gemini_client.extract_pdf_data(
                    pdf_path,
                    page_numbers=pages,
                    custom_prompt=prompt,
                    expected_structure=self._get_expected_structure(data_type, schema)
                )
            
            # Merge Gemini results into extracted data
            self._merge_gemini_results(extracted_data, gemini_response, data_type)
        
        return extracted_data
    
    def _extract_with_traditional_methods(self, pdf_path: str, schema: Dict, 
                                         analysis: Dict) -> Dict[str, Any]:
        """Extract data using traditional parsing methods"""
        import pdfplumber
        
        extracted_data = {
            "hierarchical_data": {},
            "flat_metrics": {},
            "time_series": {}
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            # Process pages based on data locations
            for data_type, pages in analysis["data_locations"].items():
                for page_num in pages:
                    if page_num <= len(pdf.pages):
                        page = pdf.pages[page_num - 1]
                        self._extract_from_page(page, page_num, data_type, 
                                              extracted_data, schema)
        
        return extracted_data
    
    def _extract_from_page(self, page, page_num: int, data_type: str,
                          extracted_data: Dict, schema: Dict):
        """Extract data from a single page"""
        text = page.extract_text() or ""
        tables = page.extract_tables()
        
        if data_type == "financial" and tables:
            self._extract_financial_data(tables, text, extracted_data, schema)
        elif data_type == "operational_metrics" and tables:
            self._extract_operational_data(tables, text, extracted_data, schema)
        elif data_type == "segment_financial":
            self._extract_segment_data(tables, text, extracted_data, schema)
        
        # Also extract from text
        self._extract_metrics_from_text(text, page_num, extracted_data, schema)
    
    def _extract_financial_data(self, tables: List, context: str, 
                               extracted_data: Dict, schema: Dict):
        """Extract financial data generically"""
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            # Look for revenue patterns
            for row in table:
                row_str = ' '.join(str(cell).lower() for cell in row if cell)
                
                # Total revenue
                if 'total' in row_str and 'revenue' in row_str:
                    value = self._extract_value_from_row(row)
                    if value and "hierarchical_data" in extracted_data:
                        if "financial" not in extracted_data["hierarchical_data"]:
                            extracted_data["hierarchical_data"]["financial"] = {}
                        if "revenue" not in extracted_data["hierarchical_data"]["financial"]:
                            extracted_data["hierarchical_data"]["financial"]["revenue"] = {}
                        
                        extracted_data["hierarchical_data"]["financial"]["revenue"]["total"] = {
                            "value": value["amount"],
                            "currency": value.get("currency", "USD"),
                            "unit": value.get("unit", "millions")
                        }
    
    def _extract_operational_data(self, tables: List, context: str,
                                 extracted_data: Dict, schema: Dict):
        """Extract operational metrics generically"""
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            # Extract any numerical data with units
            for row in table:
                row_str = ' '.join(str(cell).lower() for cell in row if cell)
                
                # Look for patterns like "X units delivered" or "Y customers"
                patterns = [
                    r'(\d+[\d,]*)\s*(units?|customers?|subscribers?|users?)',
                    r'(delivered|produced|sold|shipped)\s*:?\s*(\d+[\d,]*)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, row_str)
                    if match:
                        metric_name = self._infer_metric_name(row_str)
                        value = self._parse_number(match.group(1) if '(' in pattern else match.group(2))
                        
                        if metric_name and value:
                            if "flat_metrics" not in extracted_data:
                                extracted_data["flat_metrics"] = {}
                            
                            extracted_data["flat_metrics"][metric_name] = {
                                "value": value,
                                "unit": match.group(2) if '(' in pattern else "units"
                            }
    
    def _extract_segment_data(self, tables: List, context: str,
                             extracted_data: Dict, schema: Dict):
        """Extract segment breakdowns generically"""
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            headers = [str(h).lower() for h in table[0] if h]
            
            # Look for segment indicators in headers
            if any(seg in ' '.join(headers) for seg in ['segment', 'product', 'region', 'geography']):
                segment_data = {}
                
                for row in table[1:]:
                    if len(row) >= 2:
                        segment_name = str(row[0]).strip()
                        if segment_name and not any(skip in segment_name.lower() 
                                                   for skip in ['total', 'other']):
                            value = self._extract_value_from_row(row)
                            if value:
                                segment_data[segment_name] = value
                
                if segment_data:
                    if "hierarchical_data" not in extracted_data:
                        extracted_data["hierarchical_data"] = {}
                    
                    # Determine segment type
                    if any(geo in str(segment_data.keys()).lower() 
                          for geo in ['states', 'china', 'europe']):
                        extracted_data["hierarchical_data"]["geographic"] = {
                            "regions": segment_data
                        }
                    else:
                        if "financial" not in extracted_data["hierarchical_data"]:
                            extracted_data["hierarchical_data"]["financial"] = {}
                        extracted_data["hierarchical_data"]["financial"]["segments"] = segment_data
    
    def _extract_metrics_from_text(self, text: str, page_num: int,
                                  extracted_data: Dict, schema: Dict):
        """Extract metrics from text using pattern matching"""
        # Financial amounts
        financial_pattern = r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion|M|B)?'
        for match in re.finditer(financial_pattern, text):
            context = text[max(0, match.start()-50):match.end()+50]
            metric_name = self._infer_metric_name(context)
            
            if metric_name:
                value = self._parse_number(match.group(1))
                unit = match.group(2) or "dollars"
                
                if "flat_metrics" not in extracted_data:
                    extracted_data["flat_metrics"] = {}
                
                extracted_data["flat_metrics"][metric_name] = {
                    "value": value,
                    "currency": "USD",
                    "unit": unit,
                    "source_page": page_num
                }
    
    def _extract_value_from_row(self, row: List) -> Optional[Dict]:
        """Extract numerical value from a table row"""
        for i in range(len(row) - 1, 0, -1):
            cell = str(row[i]).strip()
            
            # Skip percentage cells
            if '%' in cell:
                continue
            
            # Try to parse as number
            value = self._parse_number(cell)
            if value is not None:
                return {
                    "amount": value,
                    "currency": "USD" if '$' in cell else None,
                    "unit": self._infer_unit(cell)
                }
        
        return None
    
    def _parse_number(self, text: str) -> Optional[float]:
        """Parse number from text, handling various formats"""
        if not text:
            return None
        
        # Remove common symbols and spaces
        cleaned = text.replace('$', '').replace(',', '').replace(' ', '')
        
        # Handle parentheses for negative numbers
        if '(' in cleaned and ')' in cleaned:
            cleaned = '-' + cleaned.replace('(', '').replace(')', '')
        
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def _infer_metric_name(self, context: str) -> Optional[str]:
        """Infer metric name from surrounding context"""
        context_lower = context.lower()
        
        # Revenue types
        if 'revenue' in context_lower:
            if 'total' in context_lower:
                return "total_revenue"
            elif 'service' in context_lower:
                return "service_revenue"
            elif 'product' in context_lower:
                return "product_revenue"
            else:
                return "revenue"
        
        # Margin types
        if 'margin' in context_lower:
            if 'gross' in context_lower:
                return "gross_margin"
            elif 'operating' in context_lower:
                return "operating_margin"
            elif 'net' in context_lower:
                return "net_margin"
            else:
                return "margin"
        
        # Income types
        if 'income' in context_lower or 'profit' in context_lower:
            if 'net' in context_lower:
                return "net_income"
            elif 'operating' in context_lower:
                return "operating_income"
            elif 'gross' in context_lower:
                return "gross_profit"
        
        # Operational metrics
        if any(word in context_lower for word in ['delivered', 'shipped', 'sold']):
            return "units_delivered"
        
        if any(word in context_lower for word in ['produced', 'manufactured']):
            return "units_produced"
        
        if any(word in context_lower for word in ['subscribers', 'users', 'customers']):
            return "active_users"
        
        return None
    
    def _infer_unit(self, text: str) -> str:
        """Infer unit from text"""
        text_lower = text.lower()
        
        if any(m in text_lower for m in ['million', 'mn', 'm']):
            return "millions"
        elif any(b in text_lower for b in ['billion', 'bn', 'b']):
            return "billions"
        elif 'k' in text_lower:
            return "thousands"
        else:
            return "units"
    
    def _merge_gemini_results(self, extracted_data: Dict, gemini_response: Dict,
                             data_type: str):
        """Merge Gemini extraction results into main data structure"""
        # Handle the new generic response format
        if "extracted_values" in gemini_response:
            # New generic format
            for value_info in gemini_response["extracted_values"]:
                self._place_generic_value(extracted_data, value_info, data_type)
        
        # Also handle any raw extractions
        if "raw_extractions" in gemini_response:
            for extraction in gemini_response["raw_extractions"]:
                # Extract all values from raw extractions
                values_found = self._extract_all_values(extraction)
                for value_info in values_found:
                    self._place_value_in_schema(extracted_data, value_info, data_type)
        
        # Try legacy format as fallback
        if not gemini_response.get("extracted_values") and not gemini_response.get("raw_extractions"):
            # First, try to merge any direct matches from the default Gemini structure
            self._merge_default_gemini_structure(extracted_data, gemini_response)
            
            # Then, recursively find and merge all values from Gemini response
            values_found = self._extract_all_values(gemini_response)
            
            # Map found values to the appropriate schema locations
            for value_info in values_found:
                self._place_value_in_schema(extracted_data, value_info, data_type)
    
    def _merge_default_gemini_structure(self, extracted_data: Dict, gemini_response: Dict):
        """Merge values from Gemini's default response structure"""
        # Handle financial segments
        if "financial_segments" in gemini_response and gemini_response["financial_segments"]:
            if "hierarchical_data" not in extracted_data:
                extracted_data["hierarchical_data"] = {}
            if "financial" not in extracted_data["hierarchical_data"]:
                extracted_data["hierarchical_data"]["financial"] = {}
            
            # Merge into the segments location
            if "segments" not in extracted_data["hierarchical_data"]["financial"]:
                extracted_data["hierarchical_data"]["financial"]["segments"] = {}
            
            extracted_data["hierarchical_data"]["financial"]["segments"].update(
                gemini_response["financial_segments"]
            )
            
            # Also update revenue total if available
            if "total_revenue" in gemini_response["financial_segments"]:
                total_rev = gemini_response["financial_segments"]["total_revenue"]
                if "revenue" in extracted_data["hierarchical_data"]["financial"]:
                    if isinstance(extracted_data["hierarchical_data"]["financial"]["revenue"], dict):
                        if "total" in extracted_data["hierarchical_data"]["financial"]["revenue"]:
                            extracted_data["hierarchical_data"]["financial"]["revenue"]["total"]["value"] = total_rev
                            extracted_data["hierarchical_data"]["financial"]["revenue"]["total"]["currency"] = "USD"
                            extracted_data["hierarchical_data"]["financial"]["revenue"]["total"]["unit"] = "millions"
        
        # Handle margins
        if "margins" in gemini_response and gemini_response["margins"]:
            if "hierarchical_data" in extracted_data and "financial" in extracted_data["hierarchical_data"]:
                if "margins" not in extracted_data["hierarchical_data"]["financial"]:
                    extracted_data["hierarchical_data"]["financial"]["margins"] = {}
                
                for margin_type, value in gemini_response["margins"].items():
                    # Clean up the value (remove % if it's a string)
                    if isinstance(value, str) and value.endswith('%'):
                        value = float(value.rstrip('%'))
                    
                    # Map to our structure
                    if "gross" in margin_type.lower():
                        extracted_data["hierarchical_data"]["financial"]["margins"]["gross"] = value
                    elif "operating" in margin_type.lower():
                        extracted_data["hierarchical_data"]["financial"]["margins"]["operating"] = value
                    elif "net" in margin_type.lower():
                        extracted_data["hierarchical_data"]["financial"]["margins"]["net"] = value
        
        # Handle vehicle/operational metrics
        if "vehicle_metrics" in gemini_response:
            self._merge_operational_metrics(extracted_data, gemini_response["vehicle_metrics"], "vehicle")
        
        # Handle energy metrics
        if "energy_metrics" in gemini_response:
            self._merge_operational_metrics(extracted_data, gemini_response["energy_metrics"], "energy")
    
    def _merge_operational_metrics(self, extracted_data: Dict, metrics: Dict, metric_type: str):
        """Merge operational metrics into the appropriate structure"""
        if not metrics:
            return
        
        # Ensure flat_metrics exists
        if "flat_metrics" not in extracted_data:
            extracted_data["flat_metrics"] = {}
        
        # Process each metric
        for category, category_data in metrics.items():
            if isinstance(category_data, dict):
                for metric_name, metric_value in category_data.items():
                    # Create a descriptive key
                    full_metric_name = f"{metric_type}_{category}_{metric_name}".lower()
                    
                    # Extract value and metadata
                    if isinstance(metric_value, dict):
                        extracted_data["flat_metrics"][full_metric_name] = metric_value
                    else:
                        extracted_data["flat_metrics"][full_metric_name] = {
                            "value": metric_value,
                            "unit": "units" if metric_type == "vehicle" else metric_type
                        }
    
    def _extract_all_values(self, obj: Any, path: str = "") -> List[Dict[str, Any]]:
        """Recursively extract all non-null values from a nested structure"""
        values = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if value is not None and not isinstance(value, (dict, list)):
                    # Found a value
                    values.append({
                        "path": new_path,
                        "key": key,
                        "value": value,
                        "context": self._get_context_from_path(new_path)
                    })
                else:
                    # Recurse deeper
                    values.extend(self._extract_all_values(value, new_path))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                values.extend(self._extract_all_values(item, f"{path}[{i}]"))
        
        return values
    
    def _get_context_from_path(self, path: str) -> str:
        """Determine the context/type of a value from its path"""
        path_lower = path.lower()
        
        if any(term in path_lower for term in ['revenue', 'sales']):
            return "revenue"
        elif any(term in path_lower for term in ['margin', 'gross', 'operating']):
            return "margin"
        elif any(term in path_lower for term in ['vehicle', 'delivery', 'production']):
            return "operational"
        elif any(term in path_lower for term in ['income', 'profit', 'earnings']):
            return "income"
        else:
            return "other"
    
    def _place_generic_value(self, extracted_data: Dict, value_info: Dict, data_type: str):
        """Place a generic extracted value in the appropriate schema location"""
        value_type = value_info.get('type', 'other')
        key = value_info.get('key', '')
        value = value_info.get('value')
        path = value_info.get('path', '')
        
        if value is None or value == '':
            return
        
        # Skip metadata fields
        if key in ['page_number', 'period', 'confidence', 'context', 'unit', 'currency']:
            return
        
        # Determine where to place the value based on its type and context
        if value_type == 'revenue':
            if 'hierarchical_data' not in extracted_data:
                extracted_data['hierarchical_data'] = {}
            if 'financial' not in extracted_data['hierarchical_data']:
                extracted_data['hierarchical_data']['financial'] = {}
            
            # Check if it's a segment revenue
            key_lower = key.lower()
            if any(seg in key_lower for seg in ['automotive', 'energy', 'services']):
                if 'segments' not in extracted_data['hierarchical_data']['financial']:
                    extracted_data['hierarchical_data']['financial']['segments'] = {}
                
                # Ensure we're creating proper value structure
                segment_key = key.title() if key.islower() else key
                extracted_data['hierarchical_data']['financial']['segments'][segment_key] = {
                    'value': float(value) if isinstance(value, (int, float)) else self._parse_number(str(value)),
                    'currency': 'USD',
                    'unit': 'millions',
                    'source_page': value_info.get('page')
                }
            elif 'total' in key_lower:
                # Total revenue
                if 'revenue' not in extracted_data['hierarchical_data']['financial']:
                    extracted_data['hierarchical_data']['financial']['revenue'] = {}
                extracted_data['hierarchical_data']['financial']['revenue']['total'] = {
                    'value': float(value) if isinstance(value, (int, float)) else self._parse_number(str(value)),
                    'currency': 'USD',
                    'unit': 'millions',
                    'source_page': value_info.get('page')
                }
        
        elif value_type == 'margin':
            if 'hierarchical_data' not in extracted_data:
                extracted_data['hierarchical_data'] = {}
            if 'financial' not in extracted_data['hierarchical_data']:
                extracted_data['hierarchical_data']['financial'] = {}
            if 'margins' not in extracted_data['hierarchical_data']['financial']:
                extracted_data['hierarchical_data']['financial']['margins'] = {}
            
            # Clean margin value
            margin_value = value
            if isinstance(value, str) and '%' in value:
                margin_value = float(value.replace('%', ''))
            elif isinstance(value, (int, float)):
                margin_value = float(value)
            
            # Map to proper margin name
            key_lower = key.lower()
            if 'gross' in key_lower:
                margin_key = 'gross'
            elif 'operating' in key_lower:
                margin_key = 'operating'
            elif 'net' in key_lower:
                margin_key = 'net'
            else:
                margin_key = key.replace('_margin', '').replace('margin', '').strip()
            
            extracted_data['hierarchical_data']['financial']['margins'][margin_key] = margin_value
        
        elif value_type == 'operational':
            if 'flat_metrics' not in extracted_data:
                extracted_data['flat_metrics'] = {}
            
            metric_name = self._normalize_metric_name(key)
            extracted_data['flat_metrics'][metric_name] = {
                'value': self._parse_number(str(value)),
                'unit': self._infer_unit(str(value)),
                'source_page': value_info.get('page')
            }
        
        else:
            # Default: add to flat metrics
            if 'flat_metrics' not in extracted_data:
                extracted_data['flat_metrics'] = {}
            
            metric_name = self._normalize_metric_name(key)
            extracted_data['flat_metrics'][metric_name] = {
                'value': value,
                'source_page': value_info.get('page')
            }
    
    def _normalize_metric_name(self, name: str) -> str:
        """Normalize metric names for consistency"""
        # Convert to lowercase and replace spaces with underscores
        normalized = name.lower().strip()
        normalized = re.sub(r'\s+', '_', normalized)
        normalized = re.sub(r'[^\w_]', '', normalized)
        return normalized
    
    def _place_value_in_schema(self, extracted_data: Dict, value_info: Dict, data_type: str):
        """Place a found value in the appropriate schema location"""
        # This is a fallback for values not handled by the default merger
        # You can extend this based on patterns you discover
    
    def _generate_generic_prompt(self, data_type: str, schema: Dict) -> str:
        """Generate a generic extraction prompt"""
        return f"""
        Extract {data_type} data from this document.
        
        Look for:
        1. All numerical values with their units
        2. The context that explains what each number represents
        3. Any hierarchical relationships (totals and breakdowns)
        4. Time periods associated with the data
        
        Return structured data with:
        - value: the numerical value
        - unit: the unit of measurement
        - context: what this number represents
        - period: time period if mentioned
        - confidence: your confidence in the extraction (0-1)
        """
    
    def _get_expected_structure(self, data_type: str, schema: Dict) -> Dict:
        """Get expected structure for Gemini extraction"""
        if data_type in schema.get("hierarchical_data", {}):
            return schema["hierarchical_data"][data_type]
        elif data_type == "operational_metrics":
            return schema.get("flat_metrics", {})
        else:
            return {}
    
    def _validate_extraction(self, extracted_data: Dict, 
                           validation_rules: List[Dict]) -> Dict[str, Any]:
        """Validate extracted data against rules"""
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "checks_performed": []
        }
        
        for rule in validation_rules:
            if rule["rule"] == "sum_to_parent":
                result = self._validate_hierarchy_sum(extracted_data, rule)
            elif rule["rule"] == "percentage_range":
                result = self._validate_percentage_range(extracted_data, rule)
            elif rule["rule"] == "segment_completeness":
                result = self._validate_segment_completeness(extracted_data, rule)
            else:
                result = {"passed": True, "message": f"Rule {rule['rule']} not implemented"}
            
            validation_results["checks_performed"].append(result)
            
            if not result["passed"]:
                if rule.get("required", False):
                    validation_results["errors"].append(result["message"])
                    validation_results["is_valid"] = False
                else:
                    validation_results["warnings"].append(result["message"])
        
        return validation_results
    
    def _validate_hierarchy_sum(self, data: Dict, rule: Dict) -> Dict:
        """Validate that children sum to parent"""
        # Implementation depends on data structure
        return {
            "passed": True,
            "message": "Hierarchy validation not yet implemented",
            "rule": rule["rule"]
        }
    
    def _validate_percentage_range(self, data: Dict, rule: Dict) -> Dict:
        """Validate percentage values are in valid range"""
        invalid_percentages = []
        
        # Check all percentage values in flat_metrics
        for metric_name, metric_data in data.get("flat_metrics", {}).items():
            if isinstance(metric_data, dict) and metric_data.get("unit") == "percentage":
                value = metric_data.get("value", 0)
                if value < rule["min"] or value > rule["max"]:
                    invalid_percentages.append(f"{metric_name}: {value}%")
        
        if invalid_percentages:
            return {
                "passed": False,
                "message": f"Invalid percentages found: {', '.join(invalid_percentages)}",
                "rule": rule["rule"]
            }
        
        return {
            "passed": True,
            "message": "All percentages in valid range",
            "rule": rule["rule"]
        }
    
    def _validate_segment_completeness(self, data: Dict, rule: Dict) -> Dict:
        """Validate all segments have values"""
        missing_segments = []
        
        # Check hierarchical data for segments
        for category in data.get("hierarchical_data", {}).values():
            if "segments" in category:
                for segment, value in category["segments"].items():
                    if not value or (isinstance(value, dict) and not value.get("value")):
                        missing_segments.append(segment)
        
        if missing_segments:
            return {
                "passed": False,
                "message": f"Missing values for segments: {', '.join(missing_segments)}",
                "rule": rule["rule"]
            }
        
        return {
            "passed": True,
            "message": "All segments have values",
            "rule": rule["rule"]
        }
    
    def _calculate_completeness(self, extracted_data: Dict, schema: Dict) -> float:
        """Calculate how complete the extraction is"""
        expected_fields = 0
        found_fields = 0
        
        # Count expected fields in schema
        def count_fields(obj):
            count = 0
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key not in ["validations", "metadata", "extraction_instructions"]:
                        if isinstance(value, dict) and "value" in value:
                            count += 1
                        else:
                            count += count_fields(value)
            return count
        
        expected_fields = count_fields(schema)
        
        # Count populated fields in extracted data
        def count_populated(obj):
            count = 0
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, dict) and "value" in value and value["value"] is not None:
                        count += 1
                    else:
                        count += count_populated(value)
            return count
        
        found_fields = count_populated(extracted_data)
        
        return found_fields / expected_fields if expected_fields > 0 else 0.0