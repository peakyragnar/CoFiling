"""
Segment Discovery - Find and extract segment data from SEC filings
"""
import logging
import re
from typing import Dict, List, Any, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class SegmentDiscovery:
    """
    Discovers and extracts segment information from SEC Company Facts data
    Handles both explicit segment data and implicit segment concepts
    """
    
    def __init__(self):
        # Common segment patterns in concept names
        self.segment_patterns = {
            'product': [
                r'.*(?:Automotive|Energy|Services?).*Revenue',
                r'.*Revenue.*(?:Automotive|Energy|Services?)',
                r'.*(?:Product|Segment).*Revenue',
                r'Revenue(?:From)?(?:Contract)?.*(?:Automotive|Energy|Services?)',
            ],
            'geographic': [
                r'.*Revenue.*(?:Domestic|Foreign|International)',
                r'.*(?:UnitedStates|US|China|Europe|Asia).*Revenue',
                r'.*Geographic.*Revenue',
                r'.*Revenue.*(?:Geographic|Region)',
            ],
            'customer': [
                r'.*Revenue.*(?:Retail|Wholesale|Commercial)',
                r'.*Customer.*Revenue',
                r'.*Revenue.*Customer.*Type',
            ]
        }
        
        # Known segment concepts for specific companies
        self.known_segments = {
            'tesla': {
                'product': [
                    'AutomotiveRevenue',
                    'EnergyGenerationAndStorageRevenue',
                    'ServicesAndOtherRevenue',
                    'AutomotiveSales',
                    'AutomotiveLeasing',
                    'AutomotiveRegulatoryCredits'
                ],
                'geographic': [
                    'RevenueFromContractWithCustomerExcludingAssessedTaxUnitedStates',
                    'RevenueFromContractWithCustomerExcludingAssessedTaxChina',
                    'RevenueFromContractWithCustomerExcludingAssessedTaxOtherCountries'
                ]
            }
        }
    
    def discover_segments(self, company_facts: Dict, company_name: str = None) -> Dict[str, Any]:
        """
        Discover segment data from Company Facts
        
        Args:
            company_facts: Raw Company Facts API response
            company_name: Optional company name for known segment lookup
            
        Returns:
            Dict with discovered segments by type
        """
        logger.info("Starting segment discovery")
        
        segments = {
            'explicit_segments': {},  # Facts with explicit segment dimensions
            'implicit_segments': {},  # Segment data in concept names
            'discovered_concepts': {
                'product': [],
                'geographic': [],
                'customer': [],
                'other': []
            },
            'segment_summary': {}
        }
        
        # Step 1: Look for explicit segment data in facts
        self._find_explicit_segments(company_facts, segments)
        
        # Step 2: Discover segment concepts from concept names
        self._discover_segment_concepts(company_facts, segments)
        
        # Step 3: Apply known segments if company identified
        if company_name:
            self._apply_known_segments(company_facts, company_name.lower(), segments)
        
        # Step 4: Extract segment values
        self._extract_segment_values(company_facts, segments)
        
        # Step 5: Generate summary
        self._generate_segment_summary(segments)
        
        return segments
    
    def _find_explicit_segments(self, company_facts: Dict, segments: Dict):
        """Find facts with explicit segment dimensions"""
        explicit_count = 0
        
        for namespace in ['us-gaap', 'ifrs-full', 'dei']:
            if namespace not in company_facts.get('facts', {}):
                continue
                
            for concept, concept_data in company_facts['facts'][namespace].items():
                if not isinstance(concept_data, dict) or 'units' not in concept_data:
                    continue
                    
                for unit, facts in concept_data.get('units', {}).items():
                    if not isinstance(facts, list):
                        continue
                        
                    for fact in facts:
                        if 'segment' in fact:
                            explicit_count += 1
                            
                            # Extract segment info
                            segment_info = fact['segment']
                            if isinstance(segment_info, dict):
                                dimension = segment_info.get('dimension', 'unknown')
                                value = segment_info.get('value', '')
                                
                                if dimension not in segments['explicit_segments']:
                                    segments['explicit_segments'][dimension] = {}
                                
                                if value not in segments['explicit_segments'][dimension]:
                                    segments['explicit_segments'][dimension][value] = []
                                
                                segments['explicit_segments'][dimension][value].append({
                                    'concept': concept,
                                    'value': fact.get('val'),
                                    'period': fact.get('fy') or fact.get('end'),
                                    'unit': unit
                                })
        
        logger.info(f"Found {explicit_count} facts with explicit segment data")
    
    def _discover_segment_concepts(self, company_facts: Dict, segments: Dict):
        """Discover segment-related concepts from concept names"""
        all_concepts = set()
        
        # Collect all concept names
        for namespace in company_facts.get('facts', {}).values():
            if isinstance(namespace, dict):
                all_concepts.update(namespace.keys())
        
        logger.info(f"Analyzing {len(all_concepts)} concepts for segment patterns")
        
        # Match against patterns
        for segment_type, patterns in self.segment_patterns.items():
            for concept in all_concepts:
                for pattern in patterns:
                    if re.match(pattern, concept, re.IGNORECASE):
                        segments['discovered_concepts'][segment_type].append(concept)
                        break
        
        # Log discoveries
        for seg_type, concepts in segments['discovered_concepts'].items():
            if concepts:
                logger.info(f"Found {len(concepts)} {seg_type} segment concepts")
    
    def _apply_known_segments(self, company_facts: Dict, company_name: str, segments: Dict):
        """Apply known segment mappings for specific companies"""
        if company_name not in self.known_segments:
            return
            
        known = self.known_segments[company_name]
        
        for segment_type, concept_list in known.items():
            # Check which known concepts exist in the data
            for concept in concept_list:
                # Check each namespace
                for namespace in company_facts.get('facts', {}).values():
                    if isinstance(namespace, dict) and concept in namespace:
                        if concept not in segments['discovered_concepts'][segment_type]:
                            segments['discovered_concepts'][segment_type].append(concept)
                            logger.info(f"Added known {segment_type} concept: {concept}")
    
    def _extract_segment_values(self, company_facts: Dict, segments: Dict):
        """Extract actual values for discovered segment concepts"""
        segments['implicit_segments'] = {
            'product': defaultdict(list),
            'geographic': defaultdict(list),
            'customer': defaultdict(list),
            'other': defaultdict(list)
        }
        
        # Extract values for each discovered concept
        for segment_type, concepts in segments['discovered_concepts'].items():
            for concept in concepts:
                # Find the concept in facts
                for namespace in company_facts.get('facts', {}).values():
                    if isinstance(namespace, dict) and concept in namespace:
                        concept_data = namespace[concept]
                        
                        # Extract recent values
                        recent_values = self._get_recent_values(concept_data)
                        if recent_values:
                            segments['implicit_segments'][segment_type][concept] = recent_values
    
    def _get_recent_values(self, concept_data: Dict, years_back: int = 3) -> List[Dict]:
        """Get recent values for a concept"""
        if not isinstance(concept_data, dict) or 'units' not in concept_data:
            return []
            
        values = []
        current_year = 2025  # Should be dynamic in production
        
        for unit, facts in concept_data.get('units', {}).items():
            if not isinstance(facts, list):
                continue
                
            for fact in facts:
                # Extract year
                year = None
                if 'fy' in fact:
                    year = fact['fy']
                elif 'end' in fact and len(str(fact['end'])) >= 4:
                    year = int(str(fact['end'])[:4])
                
                # Include if recent
                if year and year >= (current_year - years_back):
                    values.append({
                        'value': fact.get('val'),
                        'year': year,
                        'period': fact.get('fp', ''),
                        'unit': unit,
                        'filed': fact.get('filed', '')
                    })
        
        # Sort by year descending
        values.sort(key=lambda x: x['year'], reverse=True)
        
        return values[:10]  # Return most recent 10 values
    
    def _generate_segment_summary(self, segments: Dict):
        """Generate summary of discovered segments"""
        summary = {
            'has_explicit_segments': bool(segments['explicit_segments']),
            'explicit_dimensions': list(segments['explicit_segments'].keys()),
            'discovered_product_segments': len(segments['discovered_concepts']['product']),
            'discovered_geographic_segments': len(segments['discovered_concepts']['geographic']),
            'total_segment_concepts': sum(len(concepts) for concepts in segments['discovered_concepts'].values()),
            'segment_types_found': [k for k, v in segments['discovered_concepts'].items() if v]
        }
        
        segments['segment_summary'] = summary
        
        logger.info(f"Segment discovery complete:")
        logger.info(f"  - Explicit segments: {summary['has_explicit_segments']}")
        logger.info(f"  - Product segments: {summary['discovered_product_segments']}")
        logger.info(f"  - Geographic segments: {summary['discovered_geographic_segments']}")
        logger.info(f"  - Total concepts: {summary['total_segment_concepts']}")