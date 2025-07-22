"""XBRL/XML parser for extracting structured data from SEC filings"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
import json

class XBRLParser:
    """Parser for XBRL data from SEC filings"""
    
    def parse_company_facts(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse company facts JSON data from SEC API
        
        Args:
            raw_data: Raw JSON data from SEC Company Facts API
            
        Returns:
            Structured dictionary with facts and segments
        """
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
                    
                    if period and value is not None:
                        fact_list.append({
                            "period": period,
                            "value": value,
                            "unit": unit
                        })
                        fact_count += 1
                    
                    # Handle segments (dimensions)
                    if 'segment' in v:
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