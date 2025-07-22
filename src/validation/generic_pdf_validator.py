"""
Generic PDF Validator - Validates any earnings report extraction
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class GenericPDFValidator:
    """
    Validates PDF extraction results for any company
    No hardcoded expectations - validates based on structure and consistency
    """
    
    def validate_extraction(self, pdf_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate PDF extraction results
        
        Args:
            pdf_data: Extracted PDF data from GenericEarningsParser
            
        Returns:
            Validation results with detailed checks
        """
        logger.info("Validating generic PDF extraction results")
        
        results = {
            'is_complete': True,
            'completeness_score': 0.0,
            'detailed_checks': {},
            'data_quality': {},
            'consistency_checks': {},
            'recommendations': [],
            'summary': {}
        }
        
        # Extract components from the generic structure
        if isinstance(pdf_data, dict) and 'data' in pdf_data:
            # New generic structure
            extracted_data = pdf_data['data']
            metadata = pdf_data.get('metadata', {})
            document_analysis = pdf_data.get('document_analysis', {})
            validation_info = pdf_data.get('validation', {})
        else:
            # Direct data structure
            extracted_data = pdf_data
            metadata = {}
            document_analysis = {}
            validation_info = {}
        
        # Perform validation checks
        
        # 1. Structure validation
        structure_check = self._validate_structure(extracted_data)
        results['detailed_checks']['structure'] = structure_check
        
        # 2. Data completeness validation
        completeness_check = self._validate_completeness(extracted_data, document_analysis)
        results['detailed_checks']['completeness'] = completeness_check
        
        # 3. Hierarchical consistency
        if 'hierarchical_data' in extracted_data:
            hierarchy_check = self._validate_hierarchies(extracted_data['hierarchical_data'])
            results['detailed_checks']['hierarchies'] = hierarchy_check
        
        # 4. Data quality checks
        quality_check = self._validate_data_quality(extracted_data)
        results['data_quality'] = quality_check
        
        # 5. Cross-reference consistency
        consistency_check = self._validate_consistency(extracted_data)
        results['consistency_checks'] = consistency_check
        
        # Calculate overall completeness score
        results['completeness_score'] = self._calculate_overall_score(results)
        
        # Determine if extraction is complete
        results['is_complete'] = (
            results['completeness_score'] >= 0.7 and
            not any(check.get('has_errors', False) for check in results['detailed_checks'].values())
        )
        
        # Generate recommendations
        results['recommendations'] = self._generate_recommendations(results, document_analysis)
        
        # Generate summary
        results['summary'] = {
            'company': metadata.get('company', 'Unknown'),
            'period': metadata.get('period', 'Unknown'),
            'extraction_method': document_analysis.get('extraction_method', 'Unknown'),
            'business_model': document_analysis.get('business_model', 'general'),
            'data_points_extracted': self._count_data_points(extracted_data),
            'hierarchies_found': document_analysis.get('hierarchies_found', 0),
            'completeness_percentage': f"{results['completeness_score']:.0%}"
        }
        
        return results
    
    def _validate_structure(self, data: Dict) -> Dict[str, Any]:
        """Validate the structure of extracted data"""
        check = {
            'has_hierarchical_data': bool(data.get('hierarchical_data')),
            'has_flat_metrics': bool(data.get('flat_metrics')),
            'has_time_series': bool(data.get('time_series')),
            'structure_score': 0.0,
            '_summary': {}
        }
        
        # Check hierarchical data structure
        if check['has_hierarchical_data']:
            hierarchical = data['hierarchical_data']
            check['hierarchical_categories'] = list(hierarchical.keys())
            check['hierarchical_depth'] = self._measure_hierarchy_depth(hierarchical)
        
        # Check flat metrics
        if check['has_flat_metrics']:
            check['metric_count'] = len(data['flat_metrics'])
            check['metrics_with_values'] = sum(
                1 for m in data['flat_metrics'].values()
                if isinstance(m, dict) and m.get('value') is not None
            )
        
        # Calculate structure score
        scores = []
        if check['has_hierarchical_data']:
            scores.append(1.0)
        if check['has_flat_metrics'] and check.get('metric_count', 0) > 0:
            scores.append(check['metrics_with_values'] / check['metric_count'])
        
        check['structure_score'] = sum(scores) / len(scores) if scores else 0.0
        
        check['_summary'] = {
            'score': check['structure_score'],
            'has_data': check['has_hierarchical_data'] or check['has_flat_metrics']
        }
        
        return check
    
    def _validate_completeness(self, data: Dict, analysis: Dict) -> Dict[str, Any]:
        """Validate completeness based on document analysis"""
        check = {
            'expected_vs_extracted': {},
            'extraction_rate': 0.0,
            '_summary': {}
        }
        
        # Get expected metrics from analysis
        expected_operational = analysis.get('discovered_metrics', {}).get('operational', [])
        expected_financial = analysis.get('discovered_metrics', {}).get('financial', [])
        expected_segments = analysis.get('discovered_metrics', {}).get('segments', [])
        
        # Count extracted metrics
        extracted_count = 0
        expected_count = len(expected_operational) + len(expected_financial) + len(expected_segments)
        
        # Check flat metrics
        if 'flat_metrics' in data:
            extracted_count += len([m for m in data['flat_metrics'].values() 
                                  if isinstance(m, dict) and m.get('value') is not None])
        
        # Check hierarchical data
        if 'hierarchical_data' in data:
            extracted_count += self._count_hierarchical_values(data['hierarchical_data'])
        
        check['expected_vs_extracted'] = {
            'expected': expected_count,
            'extracted': extracted_count
        }
        
        if expected_count > 0:
            check['extraction_rate'] = extracted_count / expected_count
        else:
            check['extraction_rate'] = 1.0 if extracted_count > 0 else 0.0
        
        check['_summary'] = {
            'rate': check['extraction_rate'],
            'complete': check['extraction_rate'] >= 0.7
        }
        
        return check
    
    def _validate_hierarchies(self, hierarchical_data: Dict) -> Dict[str, Any]:
        """Validate hierarchical data consistency"""
        check = {
            'hierarchies_validated': [],
            'validation_errors': [],
            'all_valid': True,
            '_summary': {}
        }
        
        for category, category_data in hierarchical_data.items():
            if isinstance(category_data, dict):
                # Check if it has a total and breakdown structure
                if 'total' in category_data or 'revenue' in category_data:
                    validation = self._validate_single_hierarchy(category, category_data)
                    check['hierarchies_validated'].append(validation)
                    
                    if not validation['is_valid']:
                        check['all_valid'] = False
                        check['validation_errors'].append(validation['error'])
        
        check['_summary'] = {
            'total_hierarchies': len(check['hierarchies_validated']),
            'valid_hierarchies': sum(1 for h in check['hierarchies_validated'] if h['is_valid']),
            'has_errors': not check['all_valid']
        }
        
        return check
    
    def _validate_single_hierarchy(self, name: str, hierarchy: Dict) -> Dict[str, Any]:
        """Validate a single hierarchy (e.g., revenue breakdown)"""
        validation = {
            'hierarchy_name': name,
            'is_valid': True,
            'error': None,
            'total_vs_sum': None
        }
        
        # Find total value
        total_value = None
        if 'total' in hierarchy and isinstance(hierarchy['total'], dict):
            total_value = hierarchy['total'].get('value')
        elif 'revenue' in hierarchy and isinstance(hierarchy['revenue'], dict):
            if 'total' in hierarchy['revenue']:
                total_value = hierarchy['revenue']['total'].get('value')
        
        # Find breakdown values
        breakdown_sum = 0
        breakdown_found = False
        
        for key, value in hierarchy.items():
            if key in ['segments', 'breakdown', 'regions']:
                if isinstance(value, dict):
                    for segment_name, segment_data in value.items():
                        if isinstance(segment_data, dict) and 'value' in segment_data:
                            breakdown_sum += segment_data['value'] or 0
                            breakdown_found = True
        
        # Validate if we have both total and breakdown
        if total_value is not None and breakdown_found:
            tolerance = 0.02  # 2% tolerance
            if abs(total_value - breakdown_sum) / total_value > tolerance:
                validation['is_valid'] = False
                validation['error'] = f"{name}: Total ({total_value}) != Sum of parts ({breakdown_sum})"
            
            validation['total_vs_sum'] = {
                'total': total_value,
                'sum': breakdown_sum,
                'difference': abs(total_value - breakdown_sum),
                'percentage_diff': abs(total_value - breakdown_sum) / total_value * 100
            }
        
        return validation
    
    def _validate_data_quality(self, data: Dict) -> Dict[str, Any]:
        """Validate data quality and consistency"""
        quality = {
            'numeric_data_valid': True,
            'units_consistent': True,
            'source_attribution': True,
            'confidence_scores': [],
            'issues': []
        }
        
        # Check flat metrics
        if 'flat_metrics' in data:
            for metric_name, metric_data in data['flat_metrics'].items():
                if isinstance(metric_data, dict):
                    # Check numeric validity
                    value = metric_data.get('value')
                    if value is not None and not isinstance(value, (int, float)):
                        quality['numeric_data_valid'] = False
                        quality['issues'].append(f"{metric_name} has non-numeric value")
                    
                    # Check for negative values where unexpected
                    if isinstance(value, (int, float)) and value < 0:
                        if 'margin' not in metric_name.lower() and 'loss' not in metric_name.lower():
                            quality['issues'].append(f"{metric_name} has unexpected negative value: {value}")
                    
                    # Collect confidence scores if available
                    if 'confidence' in metric_data:
                        quality['confidence_scores'].append({
                            'metric': metric_name,
                            'confidence': metric_data['confidence']
                        })
        
        # Check percentage values
        self._check_percentage_values(data, quality)
        
        # Calculate average confidence if available
        if quality['confidence_scores']:
            valid_scores = [s['confidence'] for s in quality['confidence_scores'] if s['confidence'] is not None]
            if valid_scores:
                avg_confidence = sum(valid_scores) / len(valid_scores)
                quality['average_confidence'] = avg_confidence
        
        return quality
    
    def _validate_consistency(self, data: Dict) -> Dict[str, Any]:
        """Validate cross-reference consistency"""
        consistency = {
            'margin_calculations': [],
            'growth_calculations': [],
            'all_consistent': True
        }
        
        # Check margin calculations if we have revenue and costs
        flat_metrics = data.get('flat_metrics', {})
        
        # Simple margin check
        if 'total_revenue' in flat_metrics and 'gross_profit' in flat_metrics:
            revenue = flat_metrics['total_revenue'].get('value')
            gross_profit = flat_metrics['gross_profit'].get('value')
            
            if revenue and gross_profit and revenue > 0:
                calculated_margin = (gross_profit / revenue) * 100
                
                # Check if we have a reported margin
                if 'gross_margin' in flat_metrics:
                    reported_margin = flat_metrics['gross_margin'].get('value')
                    if reported_margin:
                        margin_diff = abs(calculated_margin - reported_margin)
                        consistency['margin_calculations'].append({
                            'type': 'gross_margin',
                            'calculated': calculated_margin,
                            'reported': reported_margin,
                            'difference': margin_diff,
                            'is_consistent': margin_diff < 1.0  # 1% tolerance
                        })
                        
                        if margin_diff >= 1.0:
                            consistency['all_consistent'] = False
        
        return consistency
    
    def _calculate_overall_score(self, results: Dict) -> float:
        """Calculate overall completeness score"""
        scores = []
        
        # Structure score
        if 'structure' in results['detailed_checks']:
            scores.append(results['detailed_checks']['structure'].get('structure_score', 0))
        
        # Completeness score
        if 'completeness' in results['detailed_checks']:
            scores.append(results['detailed_checks']['completeness'].get('extraction_rate', 0))
        
        # Hierarchy validation score
        if 'hierarchies' in results['detailed_checks']:
            summary = results['detailed_checks']['hierarchies'].get('_summary', {})
            if summary.get('total_hierarchies', 0) > 0:
                hierarchy_score = summary['valid_hierarchies'] / summary['total_hierarchies']
                scores.append(hierarchy_score)
        
        # Data quality score
        quality = results.get('data_quality', {})
        quality_score = 1.0
        if quality.get('issues'):
            # Reduce score based on number of issues
            quality_score = max(0, 1.0 - (len(quality['issues']) * 0.1))
        scores.append(quality_score)
        
        # Average all scores
        return sum(scores) / len(scores) if scores else 0.0
    
    def _generate_recommendations(self, results: Dict, analysis: Dict) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Check completeness
        if results['completeness_score'] < 0.7:
            recommendations.append(
                f"Data completeness is {results['completeness_score']:.0%}. "
                "Consider re-running with enhanced extraction settings."
            )
        
        # Check hierarchies
        hierarchies = results['detailed_checks'].get('hierarchies', {})
        if hierarchies.get('validation_errors'):
            recommendations.append(
                "Hierarchical data has consistency errors. "
                "Review segment breakdowns and totals."
            )
        
        # Check data quality
        if results['data_quality'].get('issues'):
            issue_count = len(results['data_quality']['issues'])
            recommendations.append(
                f"Found {issue_count} data quality issues. "
                "Review extracted values for accuracy."
            )
        
        # Check extraction method
        if analysis.get('extraction_method') == 'traditional':
            recommendations.append(
                "Using traditional extraction. "
                "Enable Gemini for better extraction of complex data."
            )
        
        # Business model specific recommendations
        business_model = analysis.get('business_model', 'general')
        if business_model != 'general' and results['completeness_score'] < 0.8:
            recommendations.append(
                f"Detected {business_model} business model. "
                f"Ensure industry-specific metrics are captured."
            )
        
        return recommendations
    
    def _count_data_points(self, data: Dict) -> int:
        """Count total number of extracted data points"""
        count = 0
        
        # Count flat metrics
        if 'flat_metrics' in data:
            count += len([m for m in data['flat_metrics'].values() 
                         if isinstance(m, dict) and m.get('value') is not None])
        
        # Count hierarchical values
        if 'hierarchical_data' in data:
            count += self._count_hierarchical_values(data['hierarchical_data'])
        
        # Count time series points
        if 'time_series' in data and 'metrics' in data['time_series']:
            for metric_data in data['time_series']['metrics'].values():
                if isinstance(metric_data, dict) and 'values' in metric_data:
                    count += len(metric_data['values'])
        
        return count
    
    def _count_hierarchical_values(self, hierarchical: Dict) -> int:
        """Recursively count values in hierarchical structure"""
        count = 0
        
        for key, value in hierarchical.items():
            if isinstance(value, dict):
                if 'value' in value and value['value'] is not None:
                    count += 1
                else:
                    count += self._count_hierarchical_values(value)
        
        return count
    
    def _measure_hierarchy_depth(self, hierarchical: Dict, current_depth: int = 0) -> int:
        """Measure maximum depth of hierarchical structure"""
        max_depth = current_depth
        
        for value in hierarchical.values():
            if isinstance(value, dict) and not ('value' in value):
                depth = self._measure_hierarchy_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _check_percentage_values(self, data: Dict, quality: Dict):
        """Check percentage values are in valid range"""
        # Check flat metrics
        if 'flat_metrics' in data:
            for metric_name, metric_data in data['flat_metrics'].items():
                if isinstance(metric_data, dict) and metric_data.get('unit') == 'percentage':
                    value = metric_data.get('value')
                    if isinstance(value, (int, float)):
                        if value < -100 or value > 100:
                            quality['issues'].append(
                                f"{metric_name} has invalid percentage: {value}%"
                            )
        
        # Check margins in hierarchical data
        if 'hierarchical_data' in data:
            for category_data in data['hierarchical_data'].values():
                if isinstance(category_data, dict) and 'margins' in category_data:
                    for margin_name, margin_value in category_data['margins'].items():
                        if isinstance(margin_value, (int, float)):
                            if margin_value < -100 or margin_value > 100:
                                quality['issues'].append(
                                    f"{margin_name} has invalid percentage: {margin_value}%"
                                )