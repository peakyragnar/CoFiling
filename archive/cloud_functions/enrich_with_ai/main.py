"""
Cloud Function: AI Enrichment with Vertex AI
Uses Gemini to enrich SEC filing data with insights and categorizations
"""

import functions_framework
import json
import logging
from datetime import datetime
from google.cloud import bigquery, storage
import vertexai
from vertexai.generative_models import GenerativeModel
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT', 'sec-ai-466316')
LOCATION = os.environ.get('VERTEX_LOCATION', 'us-central1')
DATASET_ID = os.environ.get('DATASET_ID', 'sec_data')
MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-2.0-pro')

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel(MODEL_NAME)

@functions_framework.cloud_event
def enrich_with_ai(cloud_event):
    """
    Process SEC filing data with AI for enrichment
    Triggered by Pub/Sub message after filing is processed
    """
    
    try:
        # Parse message
        message_data = json.loads(cloud_event.data['message']['data'])
        metadata = message_data['metadata']
        stats = message_data['stats']
        sample_facts = message_data.get('sample_facts', [])
        segment_dimensions = message_data.get('segment_dimensions', [])
        
        logger.info(f"Enriching filing: {metadata['accession_number']}")
        
        # Fetch full text content for analysis
        text_content = fetch_filing_text(metadata)
        
        # Generate AI insights
        insights = generate_filing_insights(metadata, stats, sample_facts, text_content)
        
        # Categorize financial metrics
        categorized_facts = categorize_facts(sample_facts)
        
        # Extract key metrics from narrative
        extracted_metrics = extract_metrics_from_text(text_content, metadata)
        
        # Identify risks and opportunities
        risk_analysis = analyze_risks_opportunities(text_content)
        
        # Store enriched data
        store_enriched_data({
            'metadata': metadata,
            'insights': insights,
            'categorized_facts': categorized_facts,
            'extracted_metrics': extracted_metrics,
            'risk_analysis': risk_analysis,
            'enrichment_timestamp': datetime.now().isoformat()
        })
        
        return {
            'status': 'success',
            'accession_number': metadata['accession_number'],
            'insights_generated': len(insights)
        }
        
    except Exception as e:
        logger.error(f"Error in AI enrichment: {e}")
        return {'status': 'error', 'error': str(e)}

def fetch_filing_text(metadata):
    """Fetch filing text from BigQuery"""
    
    try:
        client = bigquery.Client(project=PROJECT_ID)
        
        query = f"""
        SELECT full_text, pdf_text, management_discussion
        FROM `{PROJECT_ID}.{DATASET_ID}.texts`
        WHERE cik = @cik
          AND filing_date = @filing_date
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('cik', 'STRING', metadata['cik']),
                bigquery.ScalarQueryParameter('filing_date', 'STRING', metadata['filing_date'])
            ]
        )
        
        results = client.query(query, job_config=job_config).result()
        
        for row in results:
            # Combine all text sources
            text = f"{row.full_text or ''}\n\n{row.pdf_text or ''}\n\n{row.management_discussion or ''}"
            return text[:50000]  # Limit to 50k chars for AI processing
        
        return ""
        
    except Exception as e:
        logger.error(f"Error fetching text: {e}")
        return ""

def generate_filing_insights(metadata, stats, sample_facts, text_content):
    """Generate high-level insights about the filing"""
    
    prompt = f"""
    Analyze this SEC filing and provide key insights:
    
    Company: {metadata.get('entity_name', 'Unknown')}
    Filing Type: {metadata.get('filing_type', '10-Q')}
    Period: {metadata.get('filing_date', 'Unknown')}
    
    Statistics:
    - Total Facts: {stats.get('total_facts', 0)}
    - Segmented Facts: {stats.get('segmented_facts', 0)}
    - Unique Concepts: {stats.get('unique_concepts', 0)}
    
    Sample Financial Data:
    {json.dumps(sample_facts[:5], indent=2)}
    
    Narrative Excerpt:
    {text_content[:2000]}
    
    Provide:
    1. Key financial highlights (3-5 bullet points)
    2. Notable changes or trends
    3. Segment performance summary
    4. Forward-looking statements
    5. Overall financial health assessment
    
    Format as JSON with keys: highlights, trends, segments, outlook, health_score (1-10)
    """
    
    try:
        response = model.generate_content(prompt)
        
        # Parse response
        try:
            insights = json.loads(response.text)
        except:
            # Fallback if JSON parsing fails
            insights = {
                'highlights': [response.text[:200]],
                'trends': 'Analysis generated',
                'segments': 'See detailed segment data',
                'outlook': 'Review filing for details',
                'health_score': 7
            }
        
        return insights
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return {
            'highlights': ['Error generating AI insights'],
            'trends': str(e),
            'segments': 'N/A',
            'outlook': 'N/A',
            'health_score': 0
        }

def categorize_facts(facts):
    """Use AI to categorize financial facts"""
    
    if not facts:
        return []
    
    # Group facts by concept for batch processing
    concepts = list(set(f['concept'] for f in facts))
    
    prompt = f"""
    Categorize these financial concepts into standard categories:
    
    Concepts:
    {json.dumps(concepts[:50], indent=2)}
    
    Categories to use:
    - Revenue
    - Costs
    - Assets
    - Liabilities
    - Equity
    - Cash Flow
    - Profitability
    - Operational Metrics
    - Other
    
    Return JSON mapping each concept to its category.
    Example: {{"Revenues": "Revenue", "CostOfRevenue": "Costs"}}
    """
    
    try:
        response = model.generate_content(prompt)
        
        # Parse categorization
        try:
            categories = json.loads(response.text)
        except:
            categories = {}
        
        # Apply categories to facts
        categorized = []
        for fact in facts:
            fact_copy = fact.copy()
            fact_copy['category'] = categories.get(fact['concept'], 'Other')
            categorized.append(fact_copy)
        
        return categorized
        
    except Exception as e:
        logger.error(f"Error categorizing facts: {e}")
        return facts

def extract_metrics_from_text(text_content, metadata):
    """Extract additional metrics from narrative text"""
    
    prompt = f"""
    Extract key financial metrics and KPIs from this SEC filing text:
    
    {text_content[:5000]}
    
    Look for:
    1. Metrics not in XBRL tags (e.g., user counts, market share, unit sales)
    2. Forward guidance numbers
    3. Non-GAAP metrics
    4. Operational KPIs
    
    Return as JSON with structure:
    {{
        "extracted_metrics": [
            {{"name": "metric_name", "value": "value", "context": "brief context"}}
        ],
        "guidance": {{"revenue": "...", "earnings": "..."}},
        "kpis": {{"name": "value"}}
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        
        try:
            metrics = json.loads(response.text)
        except:
            metrics = {
                'extracted_metrics': [],
                'guidance': {},
                'kpis': {}
            }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error extracting metrics: {e}")
        return {'extracted_metrics': [], 'guidance': {}, 'kpis': {}}

def analyze_risks_opportunities(text_content):
    """Analyze risks and opportunities from filing text"""
    
    prompt = f"""
    Analyze this SEC filing text for risks and opportunities:
    
    {text_content[:5000]}
    
    Identify:
    1. Top 3 business risks mentioned
    2. Top 3 growth opportunities
    3. Competitive threats
    4. Regulatory concerns
    
    Return as JSON with structure:
    {{
        "risks": ["risk1", "risk2", "risk3"],
        "opportunities": ["opp1", "opp2", "opp3"],
        "competitive_threats": ["threat1"],
        "regulatory_concerns": ["concern1"]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        
        try:
            analysis = json.loads(response.text)
        except:
            analysis = {
                'risks': ['Unable to extract risks'],
                'opportunities': ['Unable to extract opportunities'],
                'competitive_threats': [],
                'regulatory_concerns': []
            }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing risks: {e}")
        return {
            'risks': [str(e)],
            'opportunities': [],
            'competitive_threats': [],
            'regulatory_concerns': []
        }

def store_enriched_data(enriched_data):
    """Store AI-enriched data in BigQuery"""
    
    try:
        client = bigquery.Client(project=PROJECT_ID)
        
        # Create enrichment table if it doesn't exist
        table_id = f"{PROJECT_ID}.{DATASET_ID}.ai_enrichments"
        
        # Prepare row for insertion
        row = {
            'cik': enriched_data['metadata']['cik'],
            'accession_number': enriched_data['metadata']['accession_number'],
            'filing_date': enriched_data['metadata']['filing_date'],
            'insights': json.dumps(enriched_data['insights']),
            'extracted_metrics': json.dumps(enriched_data['extracted_metrics']),
            'risk_analysis': json.dumps(enriched_data['risk_analysis']),
            'health_score': enriched_data['insights'].get('health_score', 0),
            'enrichment_timestamp': enriched_data['enrichment_timestamp']
        }
        
        # Insert row
        errors = client.insert_rows_json(table_id, [row])
        
        if errors:
            logger.error(f"Failed to store enrichment: {errors}")
        else:
            logger.info(f"Stored AI enrichment for {enriched_data['metadata']['accession_number']}")
            
    except Exception as e:
        logger.error(f"Error storing enriched data: {e}")

# For local testing
if __name__ == "__main__":
    # Test with sample data
    test_event = type('obj', (object,), {
        'data': {
            'message': {
                'data': json.dumps({
                    'metadata': {
                        'cik': '0001318605',
                        'entity_name': 'Tesla, Inc.',
                        'filing_type': '10-Q',
                        'filing_date': '2025-01-21',
                        'accession_number': '0001318605-25-000001'
                    },
                    'stats': {
                        'total_facts': 2000,
                        'segmented_facts': 500,
                        'unique_concepts': 150
                    },
                    'sample_facts': [
                        {'concept': 'Revenues', 'value': '21301000000', 'period_end': '2025-03-31'}
                    ],
                    'segment_dimensions': ['ProductOrServiceAxis', 'GeographicAxis']
                }).encode('utf-8')
            }
        }
    })
    
    result = enrich_with_ai(test_event)
    print(json.dumps(result, indent=2))