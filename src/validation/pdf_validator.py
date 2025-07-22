"""Validator for PDF extraction results"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class PDFValidator:
    """Validates PDF extraction results for completeness and accuracy"""
    
    def __init__(self):
        # Define expected data structure
        self.required_vehicle_metrics = {
            'production': ['Model 3/Y', 'Model S/X', 'Total'],
            'deliveries': ['Model 3/Y', 'Model S/X', 'Total']
        }
        
        self.required_energy_metrics = [
            'storage_deployed_gwh',
            'solar_deployed_mw'
        ]
        
        self.required_financial_segments = [
            'automotive_revenue',
            'energy_revenue', 
            'services_revenue',
            'total_revenue'
        ]
        
        self.required_geographic_segments = [
            'united_states',
            'china',
            'europe',
            'other'
        ]
        
        self.required_margins = [
            'total_gross_margin',
            'automotive_gross_margin',
            'operating_margin'
        ]
    
    def validate_extraction(self, pdf_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate PDF extraction results
        
        Args:
            pdf_data: Extracted PDF data
            
        Returns:
            Validation results with detailed checks
        """
        logger.info("Validating PDF extraction results")
        
        results = {
            'is_complete': True,
            'completeness_score': 0.0,
            'detailed_checks': {},
            'missing_data': [],
            'data_quality': {},
            'recommendations': []
        }
        
        # Vehicle metrics validation
        vehicle_check = self._validate_vehicle_metrics(pdf_data.get('vehicle_metrics', {}))
        results['detailed_checks']['vehicle_metrics'] = vehicle_check
        
        # Energy metrics validation
        energy_check = self._validate_energy_metrics(pdf_data.get('energy_metrics', {}))
        results['detailed_checks']['energy_metrics'] = energy_check
        
        # Financial segments validation
        financial_check = self._validate_financial_segments(pdf_data.get('financial_segments', {}))
        results['detailed_checks']['financial_segments'] = financial_check
        
        # Geographic segments validation
        geographic_check = self._validate_geographic_segments(pdf_data.get('geographic_segments', {}))
        results['detailed_checks']['geographic_segments'] = geographic_check
        
        # Margins validation
        margins_check = self._validate_margins(pdf_data.get('margins', {}))
        results['detailed_checks']['margins'] = margins_check
        
        # Data quality checks
        quality_check = self._validate_data_quality(pdf_data)
        results['data_quality'] = quality_check
        
        # Calculate overall completeness
        total_checks = 0
        passed_checks = 0
        
        for category, check in results['detailed_checks'].items():
            if '_summary' in check:
                total_checks += check['_summary']['total']
                passed_checks += check['_summary']['found']
        
        if total_checks > 0:
            results['completeness_score'] = passed_checks / total_checks
        
        # Determine if extraction is complete
        critical_missing = []
        
        # Check critical items
        if not vehicle_check.get('has_deliveries'):
            critical_missing.append('Vehicle deliveries')
        if not energy_check.get('has_storage'):
            critical_missing.append('Energy storage metrics')
        if not financial_check.get('has_revenue_breakdown'):
            critical_missing.append('Revenue breakdown by segment')
        
        results['is_complete'] = len(critical_missing) == 0 and results['completeness_score'] >= 0.8
        
        # Generate recommendations
        if critical_missing:
            results['recommendations'].append(f"Missing critical data: {', '.join(critical_missing)}")
        
        if results['completeness_score'] < 0.8:
            results['recommendations'].append(
                f"Data completeness is {results['completeness_score']:.0%}. "
                "Consider re-running with Gemini Vision for better extraction."
            )
        
        # Add specific recommendations based on missing data
        if not geographic_check.get('_summary', {}).get('found'):
            results['recommendations'].append(
                "Geographic revenue breakdown not found. This data may be in financial tables or charts."
            )
        
        if not margins_check.get('has_automotive_margin'):
            results['recommendations'].append(
                "Automotive gross margin not found. Check detailed financial sections."
            )
        
        # Summary info
        results['summary'] = {
            'extraction_method': 'Gemini Vision' if pdf_data.get('extraction_summary', {}).get('gemini_enhanced') else 'Traditional parsing',
            'pages_processed': len(pdf_data.get('metadata', {}).get('pages_with_visuals', [])),
            'total_pages': pdf_data.get('metadata', {}).get('total_pages', 0),
            'completeness_percentage': f"{results['completeness_score']:.0%}"
        }
        
        return results
    
    def _validate_vehicle_metrics(self, vehicle_data: Dict) -> Dict[str, Any]:
        """Validate vehicle production and delivery metrics"""
        check = {
            'has_production': False,
            'has_deliveries': False,
            'production_models': [],
            'delivery_models': [],
            '_summary': {'found': 0, 'total': 6}  # 3 models x 2 metrics
        }
        
        # Check production data
        if 'production' in vehicle_data and vehicle_data['production']:
            check['has_production'] = True
            for model in self.required_vehicle_metrics['production']:
                if model in vehicle_data['production']:
                    check['production_models'].append(model)
                    check['_summary']['found'] += 1
        
        # Check delivery data
        if 'deliveries' in vehicle_data and vehicle_data['deliveries']:
            check['has_deliveries'] = True
            for model in self.required_vehicle_metrics['deliveries']:
                if model in vehicle_data['deliveries']:
                    check['delivery_models'].append(model)
                    check['_summary']['found'] += 1
        
        return check
    
    def _validate_energy_metrics(self, energy_data: Dict) -> Dict[str, Any]:
        """Validate energy metrics"""
        check = {
            'has_storage': False,
            'has_solar': False,
            'storage_value': None,
            'solar_value': None,
            '_summary': {'found': 0, 'total': 2}
        }
        
        # Check storage deployment
        if 'storage_deployed_gwh' in energy_data:
            check['has_storage'] = True
            check['storage_value'] = energy_data['storage_deployed_gwh']
            check['_summary']['found'] += 1
        
        # Check solar deployment
        if 'solar_deployed_mw' in energy_data:
            check['has_solar'] = True
            check['solar_value'] = energy_data['solar_deployed_mw']
            check['_summary']['found'] += 1
        
        return check
    
    def _validate_financial_segments(self, financial_data: Dict) -> Dict[str, Any]:
        """Validate financial segment data"""
        check = {
            'has_revenue_breakdown': False,
            'segments_found': [],
            'total_matches_sum': False,
            '_summary': {'found': 0, 'total': 4}
        }
        
        segments_sum = 0
        for segment in self.required_financial_segments:
            if segment in financial_data and financial_data[segment]:
                check['segments_found'].append(segment)
                check['_summary']['found'] += 1
                
                if segment != 'total_revenue':
                    segments_sum += financial_data[segment]
        
        check['has_revenue_breakdown'] = len(check['segments_found']) >= 3
        
        # Check if total matches sum of segments
        if 'total_revenue' in financial_data and segments_sum > 0:
            tolerance = 0.01  # 1% tolerance for rounding
            check['total_matches_sum'] = abs(financial_data['total_revenue'] - segments_sum) / financial_data['total_revenue'] < tolerance
        
        return check
    
    def _validate_geographic_segments(self, geographic_data: Dict) -> Dict[str, Any]:
        """Validate geographic segment data"""
        check = {
            'has_geographic_breakdown': False,
            'regions_found': [],
            '_summary': {'found': 0, 'total': 4}
        }
        
        for region in self.required_geographic_segments:
            if region in geographic_data and geographic_data[region]:
                check['regions_found'].append(region)
                check['_summary']['found'] += 1
        
        check['has_geographic_breakdown'] = len(check['regions_found']) >= 3
        
        return check
    
    def _validate_margins(self, margins_data: Dict) -> Dict[str, Any]:
        """Validate margin data"""
        check = {
            'has_gross_margin': False,
            'has_automotive_margin': False,
            'has_operating_margin': False,
            'margins_found': [],
            '_summary': {'found': 0, 'total': 3}
        }
        
        margin_checks = {
            'total_gross_margin': 'has_gross_margin',
            'automotive_gross_margin': 'has_automotive_margin',
            'operating_margin': 'has_operating_margin'
        }
        
        for margin_key, check_key in margin_checks.items():
            if margin_key in margins_data and margins_data[margin_key]:
                check[check_key] = True
                check['margins_found'].append(margin_key)
                check['_summary']['found'] += 1
        
        return check
    
    def _validate_data_quality(self, pdf_data: Dict) -> Dict[str, Any]:
        """Validate data quality and consistency"""
        quality = {
            'has_metadata': bool(pdf_data.get('metadata')),
            'has_page_references': False,
            'numeric_data_valid': True,
            'issues': []
        }
        
        # Check for page references in data
        page_refs = 0
        for category in ['vehicle_metrics', 'energy_metrics']:
            if category in pdf_data:
                for metric_type, metrics in pdf_data[category].items():
                    if isinstance(metrics, dict):
                        for item, data in metrics.items():
                            if isinstance(data, dict) and 'page' in data:
                                page_refs += 1
        
        quality['has_page_references'] = page_refs > 0
        
        # Validate numeric data
        def check_numeric(value, name):
            if isinstance(value, dict) and 'value' in value:
                value = value['value']
            
            if value is not None and not isinstance(value, (int, float)):
                quality['numeric_data_valid'] = False
                quality['issues'].append(f"{name} has non-numeric value: {value}")
            elif isinstance(value, (int, float)) and value < 0:
                quality['issues'].append(f"{name} has negative value: {value}")
        
        # Check vehicle metrics
        if 'vehicle_metrics' in pdf_data:
            for metric_type in ['production', 'deliveries']:
                if metric_type in pdf_data['vehicle_metrics']:
                    for model, data in pdf_data['vehicle_metrics'][metric_type].items():
                        check_numeric(data, f"Vehicle {metric_type} - {model}")
        
        # Check financial data
        if 'financial_segments' in pdf_data:
            for segment, value in pdf_data['financial_segments'].items():
                check_numeric(value, f"Financial segment - {segment}")
        
        # Check margins (should be percentages)
        if 'margins' in pdf_data:
            for margin_type, value in pdf_data['margins'].items():
                if isinstance(value, (int, float)) and value > 100:
                    quality['issues'].append(f"{margin_type} seems too high: {value}%")
        
        return quality