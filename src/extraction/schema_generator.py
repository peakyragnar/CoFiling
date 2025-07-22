"""
Schema Generator - Creates dynamic extraction schemas based on document analysis
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """
    Generates extraction schemas dynamically based on document analysis
    No hardcoded expectations - adapts to what's in the document
    """
    
    def __init__(self):
        # Base schema structure that all documents will have
        self.base_schema = {
            "metadata": {
                "company": None,
                "period": None,
                "document_type": None,
                "extraction_date": None,
                "schema_version": "2.0"  # Generic schema version
            },
            "hierarchical_data": {},
            "flat_metrics": {},
            "time_series": {},
            "validations": []
        }
    
    def generate_schema(self, document_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate extraction schema based on document analysis
        
        Args:
            document_analysis: Output from DocumentAnalyzer
            
        Returns:
            Dynamic schema tailored to this specific document
        """
        logger.info("Generating extraction schema from document analysis")
        
        # Start with base schema
        schema = self.base_schema.copy()
        
        # Fill metadata
        schema["metadata"]["company"] = document_analysis["company_info"].get("name", "Unknown")
        schema["metadata"]["period"] = document_analysis["company_info"].get("period", "Unknown")
        schema["metadata"]["document_type"] = document_analysis["company_info"].get("document_type", "Earnings Report")
        schema["metadata"]["extraction_date"] = datetime.now().isoformat()
        
        # Generate hierarchical data structure
        schema["hierarchical_data"] = self._generate_hierarchical_structure(document_analysis)
        
        # Generate flat metrics structure
        schema["flat_metrics"] = self._generate_metrics_structure(document_analysis)
        
        # Generate time series structure if applicable
        if document_analysis["structure"].get("has_time_series"):
            schema["time_series"] = self._generate_time_series_structure(document_analysis)
        
        # Generate validation rules
        schema["validations"] = self._generate_validation_rules(document_analysis)
        
        # Add extraction instructions
        schema["extraction_instructions"] = self._generate_extraction_instructions(document_analysis)
        
        return schema
    
    def _generate_hierarchical_structure(self, analysis: Dict) -> Dict[str, Any]:
        """Generate schema for hierarchical data (e.g., revenue breakdowns)"""
        hierarchical = {}
        
        # Financial hierarchies
        if analysis["structure"]["has_financial_statements"]:
            hierarchical["financial"] = {
                "revenue": {
                    "total": {
                        "value": None,
                        "currency": None,
                        "unit": None,  # millions, billions
                        "source_page": None
                    },
                    "segments": {},
                    "validations": ["segments_sum_to_total"]
                },
                "costs": {
                    "total": None,
                    "breakdown": {}
                },
                "margins": {
                    "gross": None,
                    "operating": None,
                    "net": None
                }
            }
            
            # Add discovered segments
            for segment in analysis["discovered_metrics"]["segments"]:
                hierarchical["financial"]["revenue"]["segments"][segment] = {
                    "value": None,
                    "percentage_of_total": None,
                    "source_page": None
                }
        
        # Operational hierarchies
        if analysis["discovered_metrics"]["operational"]:
            hierarchical["operational"] = {}
            
            for hierarchy in analysis.get("hierarchies", []):
                if hierarchy["type"] == "operational":
                    parent = hierarchy["parent"]
                    hierarchical["operational"][parent] = {
                        "total": {
                            "value": None,
                            "unit": None,
                            "source_page": None
                        },
                        "breakdown": {}
                    }
                    
                    for child in hierarchy["children"]:
                        hierarchical["operational"][parent]["breakdown"][child] = {
                            "value": None,
                            "percentage_of_total": None
                        }
        
        # Geographic hierarchies if detected
        geo_segments = [h for h in analysis.get("hierarchies", []) 
                       if h["type"] == "geographic_segments"]
        if geo_segments:
            hierarchical["geographic"] = {
                "total": None,
                "regions": {}
            }
            for segment in geo_segments[0]["children"]:
                hierarchical["geographic"]["regions"][segment] = {
                    "value": None,
                    "percentage_of_total": None,
                    "currency": None
                }
        
        return hierarchical
    
    def _generate_metrics_structure(self, analysis: Dict) -> Dict[str, Any]:
        """Generate schema for standalone metrics"""
        metrics = {}
        
        # Operational metrics
        for metric in analysis["discovered_metrics"]["operational"]:
            metric_name = metric["name"]
            metrics[metric_name] = {
                "value": None,
                "unit": None,
                "period": analysis["company_info"].get("period"),
                "source_page": metric["page"],
                "confidence": None,
                "year_over_year_change": None
            }
        
        # Financial metrics not in hierarchies
        for metric in analysis["discovered_metrics"]["financial"]:
            if metric["name"] not in ["revenue", "segment_revenue"]:  # Avoid duplicates
                metrics[metric["name"]] = {
                    "value": None,
                    "currency": None,
                    "unit": None,
                    "source_page": metric["page"]
                }
        
        # Percentage metrics (margins, growth rates)
        for margin in analysis["discovered_metrics"].get("margins", []):
            metrics[margin] = {
                "value": None,
                "unit": "percentage",
                "benchmark": None  # For comparison
            }
        
        return metrics
    
    def _generate_time_series_structure(self, analysis: Dict) -> Dict[str, Any]:
        """Generate schema for time series data"""
        time_series = {
            "periods": [],  # Will be populated during extraction
            "metrics": {}
        }
        
        # Identify which metrics might have time series
        tables_with_time = [t for t in analysis["tables"]["classifications"]
                           if "time_series" in t["type"]]
        
        for table in tables_with_time:
            base_type = table["type"].replace("_time_series", "")
            
            if base_type == "financial":
                time_series["metrics"]["revenue_trend"] = {
                    "periods": [],
                    "values": [],
                    "unit": None
                }
            elif base_type == "operational_metrics":
                # Add operational metrics that likely have trends
                for metric in analysis["discovered_metrics"]["operational"]:
                    time_series["metrics"][f"{metric['name']}_trend"] = {
                        "periods": [],
                        "values": [],
                        "unit": None
                    }
        
        return time_series
    
    def _generate_validation_rules(self, analysis: Dict) -> List[Dict[str, Any]]:
        """Generate validation rules based on discovered data structure"""
        validations = []
        
        # Hierarchy validations
        for hierarchy in analysis.get("hierarchies", []):
            validations.append({
                "rule": "sum_to_parent",
                "parent": hierarchy["parent"],
                "children": hierarchy["children"],
                "tolerance": 0.01,  # 1% tolerance for rounding
                "required": True
            })
        
        # Percentage validations
        validations.append({
            "rule": "percentage_range",
            "fields": ["all_percentage_fields"],
            "min": -100,  # Allow negative for losses
            "max": 100,
            "required": False
        })
        
        # Cross-metric validations
        if "margins" in str(analysis["discovered_metrics"]):
            validations.append({
                "rule": "margin_calculation",
                "formula": "gross_margin = (revenue - cost_of_revenue) / revenue",
                "tolerance": 0.005,
                "required": False
            })
        
        # Time series validations
        if analysis["structure"].get("has_time_series"):
            validations.append({
                "rule": "time_series_continuity",
                "check": "no_missing_periods",
                "required": True
            })
        
        # Segment validations
        if analysis["discovered_metrics"]["segments"]:
            validations.append({
                "rule": "segment_completeness",
                "check": "all_segments_have_values",
                "required": True
            })
        
        return validations
    
    def _generate_extraction_instructions(self, analysis: Dict) -> Dict[str, Any]:
        """Generate specific instructions for extraction based on analysis"""
        instructions = {
            "primary_pages": [],
            "extraction_strategy": {},
            "special_handling": [],
            "confidence_thresholds": {}
        }
        
        # Identify primary pages for each data type
        for data_type, pages in analysis["data_locations"].items():
            instructions["primary_pages"].append({
                "data_type": data_type,
                "pages": sorted(set(pages)),
                "priority": "high" if data_type in ["financial", "operational_metrics"] else "medium"
            })
        
        # Set extraction strategy based on document structure
        if len(analysis["tables"]["classifications"]) > 5:
            instructions["extraction_strategy"]["primary_method"] = "table_focused"
            instructions["extraction_strategy"]["fallback"] = "text_extraction"
        else:
            instructions["extraction_strategy"]["primary_method"] = "mixed_extraction"
        
        # Special handling for complex structures
        if analysis.get("hierarchies"):
            instructions["special_handling"].append({
                "type": "preserve_hierarchy",
                "description": "Maintain parent-child relationships in data"
            })
        
        # Business-specific handling
        business_model = analysis.get("business_model", "general")
        if business_model == "automotive":
            instructions["special_handling"].append({
                "type": "unit_recognition",
                "description": "Distinguish between production and delivery units"
            })
        elif business_model == "technology/saas":
            instructions["special_handling"].append({
                "type": "recurring_metrics",
                "description": "Identify ARR, MRR, and subscriber metrics"
            })
        
        # Set confidence thresholds
        instructions["confidence_thresholds"] = {
            "financial_data": 0.95,  # High confidence required
            "operational_data": 0.90,
            "segment_data": 0.85,
            "time_series": 0.80
        }
        
        # Add Gemini-specific instructions
        instructions["gemini_prompts"] = self._generate_gemini_prompts(analysis)
        
        return instructions
    
    def _generate_gemini_prompts(self, analysis: Dict) -> Dict[str, str]:
        """Generate Gemini prompts based on document structure"""
        prompts = {}
        
        # Base extraction prompt
        base_prompt = f"""
        Extract data from this {analysis['company_info'].get('document_type', 'earnings report')} 
        for {analysis['company_info'].get('name', 'the company')} - {analysis['company_info'].get('period', 'period')}.
        
        The document contains the following structure:
        - {len(analysis['discovered_metrics']['operational'])} operational metrics
        - {len(analysis['discovered_metrics']['financial'])} financial metrics
        - {len(analysis['discovered_metrics']['segments'])} business segments
        """
        
        # Hierarchy-aware prompt
        if analysis.get("hierarchies"):
            hierarchy_prompt = """
            Pay special attention to hierarchical relationships:
            - Identify parent totals and their component breakdowns
            - Ensure all components are captured
            - Note the relationship between totals and subtotals
            """
            prompts["hierarchy_extraction"] = base_prompt + hierarchy_prompt
        
        # Segment extraction prompt
        if analysis["discovered_metrics"]["segments"]:
            segments = ", ".join(analysis["discovered_metrics"]["segments"][:5])
            segment_prompt = f"""
            Extract segment data for: {segments}
            For each segment, capture:
            - Revenue or relevant metric
            - Percentage of total if provided
            - Year-over-year growth if available
            """
            prompts["segment_extraction"] = base_prompt + segment_prompt
        
        # Time series prompt
        if analysis["structure"].get("has_time_series"):
            time_prompt = """
            Extract time series data:
            - Identify all time periods (quarters, years)
            - Extract values for each period
            - Maintain chronological order
            - Note if any periods are missing
            """
            prompts["time_series_extraction"] = base_prompt + time_prompt
        
        # Validation prompt
        prompts["validation"] = """
        After extraction, verify:
        1. All percentages sum to 100% where applicable
        2. Segment values sum to totals
        3. Margins are calculated correctly
        4. Time series data is complete
        Return any discrepancies found.
        """
        
        return prompts