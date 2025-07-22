"""Validation module for SEC data extraction completeness"""
from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class SECValidator:
    """Validates completeness and quality of SEC data extraction"""
    
    # Expected minimum thresholds
    MIN_CONCEPTS = 100
    MIN_FACTS = 500
    MIN_SEGMENTS = 10
    MIN_COMMON_ITEMS = 4
    
    # Critical financial items we expect to find
    CRITICAL_ITEMS = [
        'Revenues',
        'Assets', 
        'Liabilities',
        'CashAndCashEquivalents',
        'NetIncomeLoss',
        'OperatingIncomeLoss',
        'GrossProfit',
        'StockholdersEquity',
        'OperatingExpenses',
        'CostOfRevenue'
    ]
    
    # Expected segment dimensions for a complete filing
    EXPECTED_SEGMENTS = [
        'StatementBusinessSegmentsAxis',
        'ProductOrServiceAxis',
        'StatementGeographicalAxis',
        'ConsolidatedEntitiesAxis'
    ]
    
    def validate_extraction(self, raw_data: Dict[str, Any], 
                          formatted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive validation of SEC data extraction
        
        Returns:
            Validation report with detailed results
        """
        report = {
            'is_complete': False,
            'completeness_score': 0.0,
            'summary': {},
            'detailed_checks': {},
            'recommendations': []
        }
        
        # Run all validation checks
        report['summary'] = self._get_data_summary(raw_data, formatted_data)
        report['detailed_checks'] = self._run_detailed_checks(raw_data, formatted_data)
        
        # Calculate completeness score
        report['completeness_score'] = self._calculate_completeness_score(report['detailed_checks'])
        report['is_complete'] = report['completeness_score'] >= 0.8
        
        # Generate recommendations
        report['recommendations'] = self._generate_recommendations(report['detailed_checks'])
        
        return report
    
    def _get_data_summary(self, raw_data: Dict[str, Any], 
                         formatted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary statistics"""
        facts = raw_data.get('facts', {}).get('us-gaap', {})
        formatted_facts = formatted_data.get('structured', {}).get('facts', {})
        segments = formatted_data.get('structured', {}).get('segments', {})
        
        # Count segment facts
        segment_fact_count = 0
        for dimension in segments.values():
            for member_facts in dimension.values():
                segment_fact_count += len(member_facts)
        
        return {
            'company': formatted_data.get('metadata', {}).get('entityName', 'Unknown'),
            'cik': formatted_data.get('metadata', {}).get('cik', 'Unknown'),
            'total_concepts': len(facts),
            'total_facts': sum(len(entries) for entries in formatted_facts.values()),
            'segment_dimensions': len(segments),
            'segment_facts': segment_fact_count,
            'unique_periods': self._count_unique_periods(formatted_facts),
            'period_coverage': self._get_period_coverage(formatted_facts)
        }
    
    def _run_detailed_checks(self, raw_data: Dict[str, Any], 
                            formatted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run detailed validation checks"""
        facts = raw_data.get('facts', {}).get('us-gaap', {})
        segments = formatted_data.get('structured', {}).get('segments', {})
        
        checks = {
            'has_minimum_concepts': len(facts) >= self.MIN_CONCEPTS,
            'has_minimum_facts': self._count_total_facts(raw_data) >= self.MIN_FACTS,
            'has_segments': len(segments) > 0,
            'has_minimum_segments': len(segments) >= self.MIN_SEGMENTS,
            'critical_items': self._check_critical_items(facts),
            'segment_coverage': self._check_segment_coverage(segments),
            'data_consistency': self._check_data_consistency(formatted_data)
        }
        
        return checks
    
    def _check_critical_items(self, facts: Dict[str, Any]) -> Dict[str, bool]:
        """Check presence of critical financial items"""
        results = {}
        found_count = 0
        
        for item in self.CRITICAL_ITEMS:
            found = item in facts
            results[item] = found
            if found:
                found_count += 1
        
        results['_summary'] = {
            'found': found_count,
            'total': len(self.CRITICAL_ITEMS),
            'percentage': found_count / len(self.CRITICAL_ITEMS) * 100
        }
        
        return results
    
    def _check_segment_coverage(self, segments: Dict[str, Any]) -> Dict[str, Any]:
        """Check segment dimension coverage"""
        results = {
            'dimensions_found': list(segments.keys()),
            'expected_coverage': {}
        }
        
        for expected in self.EXPECTED_SEGMENTS:
            results['expected_coverage'][expected] = expected in segments
        
        results['_summary'] = {
            'found': sum(1 for v in results['expected_coverage'].values() if v),
            'expected': len(self.EXPECTED_SEGMENTS),
            'additional': len([d for d in segments if d not in self.EXPECTED_SEGMENTS])
        }
        
        return results
    
    def _check_data_consistency(self, formatted_data: Dict[str, Any]) -> Dict[str, bool]:
        """Check data consistency and quality"""
        facts = formatted_data.get('structured', {}).get('facts', {})
        
        return {
            'no_empty_facts': all(len(values) > 0 for values in facts.values()),
            'has_metadata': 'metadata' in formatted_data,
            'has_structured_data': 'structured' in formatted_data,
            'facts_have_periods': self._check_facts_have_periods(facts),
            'facts_have_values': self._check_facts_have_values(facts)
        }
    
    def _calculate_completeness_score(self, checks: Dict[str, Any]) -> float:
        """Calculate overall completeness score (0-1)"""
        scores = []
        
        # Basic checks (30%)
        basic_weight = 0.3
        basic_checks = ['has_minimum_concepts', 'has_minimum_facts', 'has_segments']
        basic_score = sum(1 for check in basic_checks if checks.get(check, False)) / len(basic_checks)
        scores.append(basic_score * basic_weight)
        
        # Critical items (40%)
        critical_weight = 0.4
        critical_score = checks['critical_items']['_summary']['percentage'] / 100
        scores.append(critical_score * critical_weight)
        
        # Segment coverage (20%)
        segment_weight = 0.2
        segment_summary = checks['segment_coverage']['_summary']
        segment_score = segment_summary['found'] / segment_summary['expected'] if segment_summary['expected'] > 0 else 0
        scores.append(segment_score * segment_weight)
        
        # Data consistency (10%)
        consistency_weight = 0.1
        consistency_checks = [v for k, v in checks['data_consistency'].items() if isinstance(v, bool)]
        consistency_score = sum(consistency_checks) / len(consistency_checks) if consistency_checks else 0
        scores.append(consistency_score * consistency_weight)
        
        return sum(scores)
    
    def _generate_recommendations(self, checks: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Check minimum requirements
        if not checks.get('has_minimum_concepts'):
            recommendations.append("Insufficient concepts extracted. Check SEC API connection.")
        
        if not checks.get('has_minimum_facts'):
            recommendations.append("Low fact count. Verify parsing logic covers all data types.")
        
        # Check critical items
        critical_summary = checks['critical_items']['_summary']
        if critical_summary['percentage'] < 80:
            missing = [item for item, found in checks['critical_items'].items() 
                      if item != '_summary' and not found]
            recommendations.append(f"Missing critical items: {', '.join(missing[:3])}")
        
        # Check segments
        if not checks.get('has_segments'):
            recommendations.append("No segment data found. Check segment parsing logic.")
        elif checks.get('has_minimum_segments', False) is False:
            recommendations.append("Limited segment dimensions. May be missing segment data.")
        
        return recommendations
    
    def _count_total_facts(self, raw_data: Dict[str, Any]) -> int:
        """Count total number of facts in raw data"""
        total = 0
        facts = raw_data.get('facts', {}).get('us-gaap', {})
        
        for concept_data in facts.values():
            units = concept_data.get('units', {})
            for unit_values in units.values():
                total += len(unit_values)
        
        return total
    
    def _count_unique_periods(self, formatted_facts: Dict[str, List[Dict]]) -> int:
        """Count unique reporting periods"""
        periods = set()
        
        for fact_list in formatted_facts.values():
            for fact in fact_list:
                if 'period' in fact:
                    periods.add(str(fact['period']))
        
        return len(periods)
    
    def _check_facts_have_periods(self, facts: Dict[str, List[Dict]]) -> bool:
        """Check if all facts have period information"""
        for fact_list in facts.values():
            for fact in fact_list:
                if 'period' not in fact:
                    return False
        return True
    
    def _check_facts_have_values(self, facts: Dict[str, List[Dict]]) -> bool:
        """Check if all facts have values"""
        for fact_list in facts.values():
            for fact in fact_list:
                if 'value' not in fact or fact['value'] is None:
                    return False
        return True
    
    def _get_period_coverage(self, formatted_facts: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """Get period coverage information"""
        years = set()
        quarters = set()
        
        for fact_list in formatted_facts.values():
            for fact in fact_list:
                period = fact.get('period')
                if period:
                    period_str = str(period)
                    # Extract year
                    if '-' in period_str:
                        year = period_str.split('-')[0]
                        if len(year) == 4 and year.isdigit():
                            years.add(int(year))
                            # Check if it's a quarterly period
                            if len(period_str) >= 10:  # YYYY-MM-DD format
                                quarters.add(period_str[:7])  # YYYY-MM
                    elif len(period_str) == 4 and period_str.isdigit():
                        years.add(int(period_str))
        
        sorted_years = sorted(years)
        
        return {
            'years': sorted_years,
            'year_range': f"{sorted_years[0]}-{sorted_years[-1]}" if sorted_years else "N/A",
            'total_years': len(years),
            'quarters_count': len(quarters)
        }