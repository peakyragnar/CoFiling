-- BigQuery Views with ML Functions for SEC Filing Analysis
-- These views use BigQuery ML to enhance the data with AI capabilities

-- Create AI enrichments table if not exists
CREATE TABLE IF NOT EXISTS `sec-ai-466316.sec_data.ai_enrichments` (
  cik STRING NOT NULL,
  accession_number STRING,
  filing_date DATE,
  insights STRING, -- JSON
  extracted_metrics STRING, -- JSON
  risk_analysis STRING, -- JSON
  health_score INT64,
  enrichment_timestamp TIMESTAMP
);

-- View 1: Enhanced Facts with AI Categorization
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.facts_enhanced` AS
WITH categorized_facts AS (
  SELECT 
    f.*,
    -- Use ML.GENERATE_TEXT to categorize concepts
    ML.GENERATE_TEXT(
      MODEL `sec-ai-466316.sec_data.gemini_pro`,
      CONCAT(
        'Categorize this financial concept into one category: Revenue, Costs, Assets, Liabilities, Equity, Cash Flow, or Other. Concept: ',
        f.concept
      ),
      STRUCT(
        0.2 AS temperature,
        100 AS max_output_tokens
      )
    ) AS ml_text_result
  FROM `sec-ai-466316.sec_data.facts` f
)
SELECT 
  *,
  REGEXP_EXTRACT(ml_text_result.text, r'(Revenue|Costs|Assets|Liabilities|Equity|Cash Flow|Other)') AS ai_category
FROM categorized_facts;

-- View 2: Company Financial Summary with Trends
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.company_summary` AS
WITH latest_metrics AS (
  SELECT 
    cik,
    entity_name,
    MAX(CASE WHEN concept = 'Revenues' THEN value END) AS latest_revenue,
    MAX(CASE WHEN concept = 'NetIncomeLoss' THEN value END) AS latest_net_income,
    MAX(CASE WHEN concept = 'Assets' THEN value END) AS total_assets,
    MAX(CASE WHEN concept = 'StockholdersEquity' THEN value END) AS total_equity,
    MAX(period_end) AS latest_period
  FROM `sec-ai-466316.sec_data.facts`
  WHERE period_end >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
  GROUP BY cik, entity_name
),
previous_metrics AS (
  SELECT 
    cik,
    MAX(CASE WHEN concept = 'Revenues' THEN value END) AS previous_revenue,
    MAX(CASE WHEN concept = 'NetIncomeLoss' THEN value END) AS previous_net_income
  FROM `sec-ai-466316.sec_data.facts`
  WHERE period_end >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR)
    AND period_end < DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
  GROUP BY cik
)
SELECT 
  l.*,
  p.previous_revenue,
  p.previous_net_income,
  SAFE_DIVIDE(l.latest_revenue - p.previous_revenue, p.previous_revenue) * 100 AS revenue_growth_pct,
  SAFE_DIVIDE(l.latest_net_income, l.latest_revenue) * 100 AS net_margin_pct,
  SAFE_DIVIDE(l.latest_net_income, l.total_equity) * 100 AS roe_pct,
  e.health_score AS ai_health_score
FROM latest_metrics l
LEFT JOIN previous_metrics p ON l.cik = p.cik
LEFT JOIN (
  SELECT cik, MAX(health_score) AS health_score
  FROM `sec-ai-466316.sec_data.ai_enrichments`
  GROUP BY cik
) e ON l.cik = e.cik;

-- View 3: Segment Performance Analysis
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.segment_performance` AS
WITH segment_trends AS (
  SELECT 
    s.cik,
    s.dimension_axis,
    s.dimension_member,
    s.concept,
    s.period_end,
    s.value,
    LAG(s.value) OVER (
      PARTITION BY s.cik, s.dimension_axis, s.dimension_member, s.concept 
      ORDER BY s.period_end
    ) AS previous_value,
    LEAD(s.period_end) OVER (
      PARTITION BY s.cik, s.dimension_axis, s.dimension_member, s.concept 
      ORDER BY s.period_end DESC
    ) AS next_period
  FROM `sec-ai-466316.sec_data.segments` s
  WHERE s.concept IN ('Revenues', 'OperatingIncomeLoss', 'CostOfRevenue')
)
SELECT 
  *,
  SAFE_DIVIDE(value - previous_value, previous_value) * 100 AS period_growth_pct,
  CASE 
    WHEN next_period IS NULL THEN 'Latest'
    ELSE 'Historical'
  END AS period_status
FROM segment_trends
WHERE value IS NOT NULL;

-- View 4: Anomaly Detection for Financial Metrics
CREATE OR REPLACE MODEL IF NOT EXISTS `sec-ai-466316.sec_data.anomaly_model`
OPTIONS(
  model_type='AUTOML_REGRESSOR',
  input_label_cols=['value']
) AS
SELECT 
  concept,
  EXTRACT(YEAR FROM period_end) AS year,
  EXTRACT(QUARTER FROM period_end) AS quarter,
  value
FROM `sec-ai-466316.sec_data.facts`
WHERE concept IN ('Revenues', 'NetIncomeLoss', 'OperatingIncomeLoss')
  AND value IS NOT NULL;

-- View with anomaly detection
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.facts_with_anomalies` AS
WITH predictions AS (
  SELECT 
    f.*,
    ML.PREDICT(MODEL `sec-ai-466316.sec_data.anomaly_model`, 
      (SELECT 
        f.concept,
        EXTRACT(YEAR FROM f.period_end) AS year,
        EXTRACT(QUARTER FROM f.period_end) AS quarter,
        f.value
      )
    ) AS prediction
  FROM `sec-ai-466316.sec_data.facts` f
  WHERE f.concept IN ('Revenues', 'NetIncomeLoss', 'OperatingIncomeLoss')
)
SELECT 
  *,
  ABS(value - prediction.predicted_value) / NULLIF(prediction.predicted_value, 0) AS deviation_pct,
  CASE 
    WHEN ABS(value - prediction.predicted_value) / NULLIF(prediction.predicted_value, 0) > 0.2 
    THEN TRUE 
    ELSE FALSE 
  END AS is_anomaly
FROM predictions;

-- View 5: AI-Generated Financial Insights
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.ai_insights_view` AS
SELECT 
  e.cik,
  f.entity_name,
  e.filing_date,
  e.health_score,
  JSON_EXTRACT_SCALAR(e.insights, '$.highlights[0]') AS key_highlight,
  JSON_EXTRACT_SCALAR(e.insights, '$.trends') AS trend_summary,
  JSON_EXTRACT_SCALAR(e.insights, '$.outlook') AS outlook,
  JSON_EXTRACT_ARRAY(e.risk_analysis, '$.risks') AS top_risks,
  JSON_EXTRACT_ARRAY(e.risk_analysis, '$.opportunities') AS top_opportunities,
  e.enrichment_timestamp
FROM `sec-ai-466316.sec_data.ai_enrichments` e
JOIN (
  SELECT DISTINCT cik, entity_name 
  FROM `sec-ai-466316.sec_data.facts`
) f ON e.cik = f.cik
ORDER BY e.enrichment_timestamp DESC;

-- View 6: Peer Comparison
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.peer_comparison` AS
WITH company_metrics AS (
  SELECT 
    cik,
    entity_name,
    MAX(CASE WHEN concept = 'Revenues' THEN value END) AS revenue,
    MAX(CASE WHEN concept = 'NetIncomeLoss' THEN value END) AS net_income,
    MAX(CASE WHEN concept = 'Assets' THEN value END) AS total_assets,
    MAX(period_end) AS latest_period
  FROM `sec-ai-466316.sec_data.facts`
  WHERE period_end >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 QUARTER)
  GROUP BY cik, entity_name
),
rankings AS (
  SELECT 
    *,
    RANK() OVER (ORDER BY revenue DESC) AS revenue_rank,
    RANK() OVER (ORDER BY net_income DESC) AS profitability_rank,
    RANK() OVER (ORDER BY total_assets DESC) AS size_rank,
    SAFE_DIVIDE(net_income, revenue) * 100 AS net_margin_pct,
    SAFE_DIVIDE(revenue, total_assets) AS asset_turnover
  FROM company_metrics
)
SELECT 
  *,
  CASE 
    WHEN revenue_rank <= 3 THEN 'Top 3'
    WHEN revenue_rank <= 10 THEN 'Top 10'
    ELSE 'Other'
  END AS revenue_tier
FROM rankings;

-- View 7: Time Series for Forecasting
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.time_series_view` AS
SELECT 
  cik,
  entity_name,
  concept,
  period_end,
  value,
  EXTRACT(YEAR FROM period_end) AS year,
  EXTRACT(QUARTER FROM period_end) AS quarter,
  ROW_NUMBER() OVER (PARTITION BY cik, concept ORDER BY period_end) AS period_sequence
FROM `sec-ai-466316.sec_data.facts`
WHERE concept IN ('Revenues', 'NetIncomeLoss', 'OperatingIncomeLoss', 'CashAndCashEquivalents')
  AND value IS NOT NULL
  AND period_end >= DATE_SUB(CURRENT_DATE(), INTERVAL 5 YEAR)
ORDER BY cik, concept, period_end;

-- Create a Gemini Pro model reference (if not exists)
-- Note: This requires setting up the model in Vertex AI first
CREATE OR REPLACE MODEL `sec-ai-466316.sec_data.gemini_pro`
REMOTE WITH CONNECTION `sec-ai-466316.us-central1.vertex_ai_connection`
OPTIONS (
  endpoint = 'gemini-2.0-pro'
);