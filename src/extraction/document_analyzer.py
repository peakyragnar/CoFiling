"""
Document Analyzer - Understands earnings report structure without hardcoded expectations
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
import re
from pathlib import Path
import pdfplumber

logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """
    Analyzes earnings reports to understand their structure and content
    without any company-specific assumptions
    """
    
    def __init__(self):
        self.section_patterns = {
            'financial': [
                r'financial\s+(results?|statements?|highlights?)',
                r'consolidated\s+statements?',
                r'income\s+statements?',
                r'balance\s+sheets?',
                r'cash\s+flows?'
            ],
            'operational': [
                r'operational\s+(metrics?|highlights?|data)',
                r'key\s+(metrics?|performance|indicators)',
                r'business\s+(metrics?|highlights?)',
                r'quarterly\s+(metrics?|highlights?)'
            ],
            'segment': [
                r'segment\s+(information|data|results?)',
                r'revenue\s+by\s+(segment|product|geography|region)',
                r'business\s+segments?',
                r'geographic\s+(segments?|breakdown|revenue)'
            ],
            'guidance': [
                r'(outlook|guidance|forecast)',
                r'forward[- ]looking',
                r'expectations?'
            ]
        }
        
        self.metric_patterns = {
            'volume': [
                r'(\d+[\d,]*)\s*(units?|deliveries|sales|sold|shipped)',
                r'(volume|quantity|count)\s*:?\s*(\d+[\d,]*)',
                r'(\d+[\d,]*)\s*(subscribers?|users?|customers?|accounts?)'
            ],
            'financial': [
                r'\$?\s*(\d+[\d,]*\.?\d*)\s*(million|billion|mn|bn|[mb])',
                r'revenue\s*:?\s*\$?\s*(\d+[\d,]*\.?\d*)',
                r'(gross|operating|net)\s*(profit|margin|income)'
            ],
            'percentage': [
                r'(\d+\.?\d*)\s*%',
                r'(margin|growth|increase|decrease)\s*:?\s*(\d+\.?\d*)\s*%'
            ],
            'ratio': [
                r'(\d+\.?\d*)[x×]\s*(multiple|ratio)?',
                r'(ratio|multiple)\s*:?\s*(\d+\.?\d*)'
            ]
        }
    
    def analyze_document(self, pdf_path: str) -> Dict[str, Any]:
        """
        Analyze document structure and content
        
        Returns:
            {
                "company_info": {
                    "name": "Company Name",
                    "period": "Q1 2025",
                    "document_type": "Earnings Release"
                },
                "structure": {
                    "total_pages": 32,
                    "sections": [...],
                    "has_financial_statements": true,
                    "has_segment_data": true
                },
                "discovered_metrics": {
                    "operational": [...],
                    "financial": [...],
                    "segments": [...]
                },
                "tables": {
                    "count": 15,
                    "classifications": [...]
                },
                "data_locations": {
                    "revenue_data": [4, 5, 23],
                    "operational_metrics": [6, 7, 8],
                    "segment_breakdown": [25, 26]
                }
            }
        """
        logger.info(f"Analyzing document structure: {pdf_path}")
        
        analysis = {
            "company_info": {},
            "structure": {
                "total_pages": 0,
                "sections": [],
                "has_financial_statements": False,
                "has_segment_data": False,
                "has_operational_metrics": False
            },
            "discovered_metrics": {
                "operational": [],
                "financial": [],
                "segments": [],
                "margins": []
            },
            "tables": {
                "count": 0,
                "classifications": []
            },
            "data_locations": {},
            "hierarchies": []
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            analysis["structure"]["total_pages"] = len(pdf.pages)
            
            # First pass: Quick scan for document info and structure
            self._extract_company_info(pdf, analysis)
            
            # Second pass: Detailed page-by-page analysis
            for page_num, page in enumerate(pdf.pages, 1):
                self._analyze_page(page, page_num, analysis)
            
            # Third pass: Identify data relationships and hierarchies
            self._identify_hierarchies(analysis)
            
            # Final pass: Classify and organize findings
            self._classify_findings(analysis)
        
        return analysis
    
    def _extract_company_info(self, pdf, analysis: Dict):
        """Extract basic company and document information"""
        # Typically on first page
        first_page_text = pdf.pages[0].extract_text() or ""
        
        # Extract company name (usually in large font on first page)
        lines = first_page_text.split('\n')[:10]  # First 10 lines
        for line in lines:
            if len(line) > 10 and not any(char.isdigit() for char in line[:5]):
                # Likely company name
                analysis["company_info"]["name"] = line.strip()
                break
        
        # Extract period (Q1 2025, FY 2024, etc.)
        period_patterns = [
            r'(Q[1-4]\s+20\d{2})',
            r'(First|Second|Third|Fourth)\s+Quarter\s+20\d{2}',
            r'(FY|Fiscal\s+Year)\s+20\d{2}',
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}'
        ]
        
        for pattern in period_patterns:
            match = re.search(pattern, first_page_text, re.IGNORECASE)
            if match:
                analysis["company_info"]["period"] = match.group(1)
                break
        
        # Detect document type
        if 'earnings' in first_page_text.lower():
            analysis["company_info"]["document_type"] = "Earnings Release"
        elif '10-q' in first_page_text.lower():
            analysis["company_info"]["document_type"] = "10-Q"
        elif '10-k' in first_page_text.lower():
            analysis["company_info"]["document_type"] = "10-K"
    
    def _analyze_page(self, page, page_num: int, analysis: Dict):
        """Analyze individual page for content and structure"""
        text = page.extract_text() or ""
        tables = page.extract_tables()
        
        # Check for section headers
        for section_type, patterns in self.section_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    analysis["structure"]["sections"].append({
                        "type": section_type,
                        "page": page_num,
                        "pattern_matched": pattern
                    })
                    
                    # Update structure flags
                    if section_type == 'financial':
                        analysis["structure"]["has_financial_statements"] = True
                    elif section_type == 'segment':
                        analysis["structure"]["has_segment_data"] = True
        
        # Analyze tables
        if tables:
            analysis["tables"]["count"] += len(tables)
            for table_idx, table in enumerate(tables):
                classification = self._classify_table(table, text)
                if classification:
                    analysis["tables"]["classifications"].append({
                        "page": page_num,
                        "table_index": table_idx,
                        "type": classification["type"],
                        "confidence": classification["confidence"],
                        "headers": classification.get("headers", [])
                    })
                    
                    # Track data locations
                    if classification["type"] not in analysis["data_locations"]:
                        analysis["data_locations"][classification["type"]] = []
                    analysis["data_locations"][classification["type"]].append(page_num)
        
        # Discover metrics mentioned in text
        self._discover_metrics(text, page_num, analysis)
    
    def _classify_table(self, table: List[List[str]], context: str) -> Optional[Dict]:
        """Classify what type of data a table contains"""
        if not table or len(table) < 2:
            return None
        
        # Convert table to string for analysis
        table_str = ' '.join(' '.join(str(cell) for cell in row if cell) for row in table).lower()
        headers = [str(cell).lower() for cell in table[0] if cell]
        
        classification = {
            "type": "unknown",
            "confidence": 0.0,
            "headers": headers
        }
        
        # Financial table indicators
        financial_indicators = ['revenue', 'income', 'profit', 'loss', 'margin', 'expense', 'cost']
        if any(indicator in table_str for indicator in financial_indicators):
            classification["type"] = "financial"
            classification["confidence"] = 0.9
            
            # Sub-classify financial tables
            if 'segment' in table_str or 'geographic' in table_str:
                classification["type"] = "segment_financial"
            elif 'margin' in table_str and '%' in table_str:
                classification["type"] = "margins"
        
        # Operational metrics table
        operational_indicators = ['units', 'delivered', 'produced', 'sold', 'volume', 'quantity']
        if any(indicator in table_str for indicator in operational_indicators):
            classification["type"] = "operational_metrics"
            classification["confidence"] = 0.85
        
        # Time series data (has quarter/year columns)
        time_indicators = [r'q[1-4]', r'20\d{2}', 'quarter', 'year', 'ytd', 'fiscal']
        if any(re.search(ind, table_str) for ind in time_indicators):
            if classification["type"] == "unknown":
                classification["type"] = "time_series"
                classification["confidence"] = 0.7
            else:
                classification["type"] += "_time_series"
        
        return classification if classification["confidence"] > 0.5 else None
    
    def _discover_metrics(self, text: str, page_num: int, analysis: Dict):
        """Discover what metrics are mentioned in the text"""
        # Look for operational metrics
        for pattern in self.metric_patterns['volume']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                metric_context = text[max(0, match.start()-50):match.end()+50]
                metric_type = self._classify_metric(metric_context, match.group())
                
                if metric_type and metric_type not in [m['name'] for m in analysis["discovered_metrics"]["operational"]]:
                    analysis["discovered_metrics"]["operational"].append({
                        "name": metric_type,
                        "page": page_num,
                        "pattern": match.group(),
                        "context": metric_context.strip()
                    })
        
        # Look for financial metrics
        for pattern in self.metric_patterns['financial']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                metric_context = text[max(0, match.start()-50):match.end()+50]
                metric_type = self._classify_financial_metric(metric_context)
                
                if metric_type and metric_type not in [m['name'] for m in analysis["discovered_metrics"]["financial"]]:
                    analysis["discovered_metrics"]["financial"].append({
                        "name": metric_type,
                        "page": page_num,
                        "pattern": match.group()
                    })
        
        # Look for segments
        segment_patterns = [
            r'([\w\s]+)\s+revenue\s*:?\s*\$?\s*\d+',
            r'revenue\s+by\s+([\w\s]+)',
            r'(automotive|energy|services?|products?|software|hardware|cloud|retail|wholesale)\s+(revenue|sales)',
            r'(united states|us|china|europe|asia|americas?|emea|apac)\s+(revenue|sales)'
        ]
        
        for pattern in segment_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                segment_name = match.group(1).strip()
                if segment_name and segment_name not in analysis["discovered_metrics"]["segments"]:
                    analysis["discovered_metrics"]["segments"].append(segment_name)
    
    def _classify_metric(self, context: str, matched_text: str) -> Optional[str]:
        """Classify what type of operational metric this is"""
        context_lower = context.lower()
        
        # Vehicle/automotive metrics
        if any(word in context_lower for word in ['vehicle', 'car', 'auto', 'deliver']):
            if 'deliver' in context_lower:
                return "vehicle_deliveries"
            elif 'produc' in context_lower:
                return "vehicle_production"
            return "vehicle_metrics"
        
        # Technology metrics
        if any(word in context_lower for word in ['subscriber', 'user', 'member', 'account']):
            return "user_metrics"
        
        # Retail metrics
        if any(word in context_lower for word in ['store', 'location', 'sold', 'transaction']):
            return "sales_metrics"
        
        # Generic
        if 'unit' in matched_text.lower():
            return "unit_metrics"
        
        return None
    
    def _classify_financial_metric(self, context: str) -> Optional[str]:
        """Classify what type of financial metric this is"""
        context_lower = context.lower()
        
        if 'revenue' in context_lower:
            if 'total' in context_lower:
                return "total_revenue"
            elif any(word in context_lower for word in ['segment', 'product', 'service']):
                return "segment_revenue"
            return "revenue"
        
        if any(word in context_lower for word in ['income', 'profit', 'earning']):
            if 'gross' in context_lower:
                return "gross_profit"
            elif 'operating' in context_lower:
                return "operating_income"
            elif 'net' in context_lower:
                return "net_income"
            return "income"
        
        if 'margin' in context_lower:
            return "margin"
        
        if any(word in context_lower for word in ['cost', 'expense']):
            return "costs"
        
        return None
    
    def _identify_hierarchies(self, analysis: Dict):
        """Identify hierarchical relationships in the data"""
        # Look for total/subtotal patterns
        hierarchies = []
        
        # Check discovered metrics for hierarchical patterns
        operational = analysis["discovered_metrics"]["operational"]
        for i, metric in enumerate(operational):
            if 'total' in metric['name'].lower():
                # Look for related sub-metrics
                sub_metrics = []
                for other in operational:
                    if other != metric and similar_context(metric['context'], other['context']):
                        sub_metrics.append(other['name'])
                
                if sub_metrics:
                    hierarchies.append({
                        "parent": metric['name'],
                        "children": sub_metrics,
                        "type": "operational"
                    })
        
        # Look for segment hierarchies
        if analysis["discovered_metrics"]["segments"]:
            # Group segments by type
            geographic = [s for s in analysis["discovered_metrics"]["segments"] 
                         if any(geo in s.lower() for geo in ['states', 'china', 'europe', 'asia'])]
            product = [s for s in analysis["discovered_metrics"]["segments"]
                      if s not in geographic]
            
            if geographic:
                hierarchies.append({
                    "parent": "Geographic Revenue",
                    "children": geographic,
                    "type": "geographic_segments"
                })
            
            if product:
                hierarchies.append({
                    "parent": "Product/Service Revenue",
                    "children": product,
                    "type": "product_segments"
                })
        
        analysis["hierarchies"] = hierarchies
    
    def _classify_findings(self, analysis: Dict):
        """Final classification and organization of findings"""
        # Determine primary business model based on discovered metrics
        operational_types = [m['name'] for m in analysis["discovered_metrics"]["operational"]]
        
        if any('vehicle' in t for t in operational_types):
            analysis["business_model"] = "automotive"
        elif any('subscriber' in t or 'user' in t for t in operational_types):
            analysis["business_model"] = "technology/saas"
        elif any('store' in t or 'transaction' in t for t in operational_types):
            analysis["business_model"] = "retail"
        else:
            analysis["business_model"] = "general"
        
        # Set flags for what types of data are available
        analysis["structure"]["has_operational_metrics"] = bool(analysis["discovered_metrics"]["operational"])
        analysis["structure"]["has_time_series"] = any('time_series' in c['type'] 
                                                       for c in analysis["tables"]["classifications"])
        
        # Create extraction recommendations
        analysis["extraction_recommendations"] = self._generate_recommendations(analysis)
    
    def _generate_recommendations(self, analysis: Dict) -> List[Dict]:
        """Generate recommendations for extraction based on analysis"""
        recommendations = []
        
        # Recommend pages for detailed extraction
        if analysis["data_locations"]:
            for data_type, pages in analysis["data_locations"].items():
                recommendations.append({
                    "action": "extract_detailed",
                    "data_type": data_type,
                    "pages": sorted(set(pages)),
                    "reason": f"Found {data_type} data on these pages"
                })
        
        # Recommend hierarchy extraction
        if analysis["hierarchies"]:
            recommendations.append({
                "action": "preserve_hierarchy",
                "hierarchies": analysis["hierarchies"],
                "reason": "Document contains hierarchical data relationships"
            })
        
        # Recommend segment extraction
        if analysis["discovered_metrics"]["segments"]:
            recommendations.append({
                "action": "extract_segments",
                "segments": analysis["discovered_metrics"]["segments"],
                "reason": "Multiple business/geographic segments detected"
            })
        
        return recommendations


def similar_context(context1: str, context2: str, threshold: float = 0.5) -> bool:
    """Check if two contexts are similar (simple implementation)"""
    words1 = set(context1.lower().split())
    words2 = set(context2.lower().split())
    
    if not words1 or not words2:
        return False
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) > threshold