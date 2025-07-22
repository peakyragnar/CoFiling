"""XBRL/XML parser for extracting structured data from SEC filings"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

class XBRLParser:
    """Parser for XBRL data from SEC filings"""
    
    def parse_company_facts(self, raw_data: Dict[str, Any], 
                            years_back: int = 5) -> Dict[str, Any]:
        """
        Parse company facts JSON data from SEC API
        
        Args:
            raw_data: Raw JSON data from SEC Company Facts API
            years_back: Number of full years to include (default: 5)
            
        Returns:
            Structured dictionary with facts and segments
        """
        # Calculate the cutoff year
        current_year = datetime.now().year
        cutoff_year = current_year - years_back
        
        print(f"Filtering for periods: {cutoff_year}-{current_year} (last {years_back} full years + current year)")
        facts = raw_data.get('facts', {}).get('us-gaap', {})
        
        formatted = {
            "metadata": {
                "cik": raw_data.get('cik'),
                "entityName": raw_data.get('entityName')
            },
            "structured": {
                "facts": {},
                "segments": {}
            }
        }
        
        segment_count = 0
        fact_count = 0
        
        for concept, data in facts.items():
            units = data.get('units', {})
            
            for unit, values in units.items():
                fact_list = []
                
                for v in values:
                    # Extract period information
                    period = (v.get('fy') or v.get('end') or 
                             v.get('instant') or v.get('start'))
                    value = v.get('val')
                    
                    # Filter by period
                    if period and value is not None:
                        # Extract year from period
                        period_year = self._extract_year_from_period(period)
                        
                        # Only include if within our date range
                        if period_year and period_year >= cutoff_year:
                            fact_list.append({
                                "period": period,
                                "value": value,
                                "unit": unit
                            })
                            fact_count += 1
                    
                    # Handle segments (dimensions) - also filter by period
                    if 'segment' in v and period:
                        period_year = self._extract_year_from_period(period)
                        
                        if period_year and period_year >= cutoff_year:
                            segment_count += 1
                            for seg in v['segment']:
                                axis = seg.get('dimension', '')
                                member = seg.get('value', '')
                                
                                if axis not in formatted["structured"]["segments"]:
                                    formatted["structured"]["segments"][axis] = {}
                                
                                if member not in formatted["structured"]["segments"][axis]:
                                    formatted["structured"]["segments"][axis][member] = []
                                
                                formatted["structured"]["segments"][axis][member].append({
                                    "concept": concept,
                                    "period": period,
                                    "value": value,
                                    "unit": unit
                                })
                
                if fact_list:
                    formatted["structured"]["facts"][concept] = fact_list
        
        print(f"✓ Parsed {fact_count} facts across {len(facts)} concepts")
        print(f"✓ Found {segment_count} segment entries across {len(formatted['structured']['segments'])} dimensions")
        
        return formatted
    
    def parse_xbrl_instance(self, xml_content: str) -> Dict[str, Any]:
        """
        Parse XBRL instance XML file
        
        Args:
            xml_content: Raw XML content from XBRL instance file
            
        Returns:
            Structured data extracted from XBRL
        """
        try:
            root = ET.fromstring(xml_content)
            
            # Extract namespaces
            namespaces = {
                'xbrli': 'http://www.xbrl.org/2003/instance',
                'us-gaap': root.tag.split('}')[0][1:] if '}' in root.tag else ''
            }
            
            facts = []
            contexts = {}
            
            # First, parse all contexts
            for context in root.findall('.//xbrli:context', namespaces):
                context_id = context.get('id')
                period_info = self._extract_period(context, namespaces)
                segment_info = self._extract_segments(context, namespaces)
                
                contexts[context_id] = {
                    'period': period_info,
                    'segments': segment_info
                }
            
            # Then parse facts
            for elem in root:
                if elem.tag.startswith('{'):
                    namespace, local_name = elem.tag[1:].split('}')
                    context_ref = elem.get('contextRef')
                    
                    if context_ref and context_ref in contexts:
                        fact = {
                            'concept': local_name,
                            'value': elem.text,
                            'context': contexts[context_ref],
                            'unit': elem.get('unitRef'),
                            'decimals': elem.get('decimals')
                        }
                        facts.append(fact)
            
            print(f"✓ Parsed {len(facts)} facts from XBRL instance")
            return {"facts": facts, "contexts": contexts}
            
        except ET.ParseError as e:
            print(f"Error parsing XBRL: {e}")
            return {}
    
    def _extract_period(self, context: ET.Element, namespaces: Dict) -> Dict[str, str]:
        """Extract period information from context"""
        period = context.find('.//xbrli:period', namespaces)
        if period is not None:
            instant = period.find('xbrli:instant', namespaces)
            if instant is not None:
                return {'type': 'instant', 'date': instant.text}
            
            start = period.find('xbrli:startDate', namespaces)
            end = period.find('xbrli:endDate', namespaces)
            if start is not None and end is not None:
                return {
                    'type': 'duration',
                    'start': start.text,
                    'end': end.text
                }
        return {}
    
    def _extract_segments(self, context: ET.Element, namespaces: Dict) -> List[Dict[str, str]]:
        """Extract segment information from context"""
        segments = []
        entity = context.find('.//xbrli:entity', namespaces)
        if entity is not None:
            segment = entity.find('xbrli:segment', namespaces)
            if segment is not None:
                for member in segment:
                    dimension = member.get('dimension', '')
                    value = member.text or ''
                    if dimension and value:
                        segments.append({
                            'dimension': dimension,
                            'value': value
                        })
        return segments
    
    def _extract_year_from_period(self, period: Any) -> Optional[int]:
        """Extract year from various period formats"""
        if not period:
            return None
            
        period_str = str(period)
        
        # Handle different period formats
        try:
            # Format: YYYY (fiscal year)
            if len(period_str) == 4 and period_str.isdigit():
                return int(period_str)
            
            # Format: YYYY-MM-DD (dates)
            if '-' in period_str:
                year_part = period_str.split('-')[0]
                if len(year_part) == 4 and year_part.isdigit():
                    return int(year_part)
            
            # Format: YYYYMMDD
            if len(period_str) == 8 and period_str.isdigit():
                return int(period_str[:4])
            
            # Format: CY2024Q1 or FY2024
            if 'Y' in period_str.upper():
                # Extract year after Y
                parts = period_str.upper().split('Y')
                if len(parts) > 1:
                    year_str = parts[1][:4]
                    if year_str.isdigit():
                        return int(year_str)
                        
        except (ValueError, IndexError):
            pass
            
        return None