-- BigQuery Schema for SEC Filing Analysis System
-- Project: sec-ai-466316
-- Dataset: sec_data

-- Drop existing tables if needed (for clean setup)
-- DROP TABLE IF EXISTS `sec-ai-466316.sec_data.facts`;
-- DROP TABLE IF EXISTS `sec-ai-466316.sec_data.texts`;
-- DROP TABLE IF EXISTS `sec-ai-466316.sec_data.segments`;
-- DROP TABLE IF EXISTS `sec-ai-466316.sec_data.filing_status`;

-- Create facts table with proper schema
CREATE TABLE IF NOT EXISTS `sec-ai-466316.sec_data.facts` (
  cik STRING NOT NULL,
  entity_name STRING,
  filing_date DATE,
  period_end DATE,
  concept STRING NOT NULL,
  value NUMERIC,
  unit STRING,
  segment_dimension STRING,
  segment_member STRING,
  context_id STRING,
  source STRING NOT NULL, -- 'sec_api', 'xbrl_instance', 'pdf'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Create segments table (normalized structure)
CREATE TABLE IF NOT EXISTS `sec-ai-466316.sec_data.segments` (
  cik STRING NOT NULL,
  filing_date DATE,
  dimension_axis STRING NOT NULL,
  dimension_member STRING NOT NULL,
  concept STRING NOT NULL,
  period_end DATE,
  value NUMERIC,
  unit STRING,
  context_id STRING,
  source STRING NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Create texts table for narrative content
CREATE TABLE IF NOT EXISTS `sec-ai-466316.sec_data.texts` (
  cik STRING NOT NULL,
  entity_name STRING,
  filing_date DATE NOT NULL,
  filing_type STRING, -- '10-K', '10-Q', '8-K'
  accession_number STRING,
  full_text STRING,
  pdf_text STRING,
  management_discussion STRING,
  risk_factors STRING,
  source_urls ARRAY<STRING>,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Create filing status table for tracking
CREATE TABLE IF NOT EXISTS `sec-ai-466316.sec_data.filing_status` (
  cik STRING NOT NULL,
  filing_date DATE NOT NULL,
  filing_type STRING,
  accession_number STRING,
  fetch_status STRING, -- 'pending', 'processing', 'completed', 'failed'
  facts_count INT64,
  segments_count INT64,
  error_message STRING,
  processing_time_seconds FLOAT64,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_facts_cik_period 
ON `sec-ai-466316.sec_data.facts`(cik, period_end);

CREATE INDEX IF NOT EXISTS idx_segments_cik_dimension 
ON `sec-ai-466316.sec_data.segments`(cik, dimension_axis, dimension_member);

CREATE INDEX IF NOT EXISTS idx_texts_cik_filing 
ON `sec-ai-466316.sec_data.texts`(cik, filing_date);

-- Create view for latest facts per company
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.latest_facts` AS
SELECT 
  f.*,
  ROW_NUMBER() OVER (
    PARTITION BY f.cik, f.concept 
    ORDER BY f.period_end DESC, f.created_at DESC
  ) as recency_rank
FROM `sec-ai-466316.sec_data.facts` f
WHERE recency_rank = 1;

-- Create view for segment analysis
CREATE OR REPLACE VIEW `sec-ai-466316.sec_data.segment_analysis` AS
SELECT 
  s.cik,
  s.dimension_axis,
  s.dimension_member,
  s.concept,
  s.period_end,
  s.value,
  s.unit,
  LAG(s.value) OVER (
    PARTITION BY s.cik, s.dimension_axis, s.dimension_member, s.concept 
    ORDER BY s.period_end
  ) as previous_value,
  (s.value - LAG(s.value) OVER (
    PARTITION BY s.cik, s.dimension_axis, s.dimension_member, s.concept 
    ORDER BY s.period_end
  )) / NULLIF(LAG(s.value) OVER (
    PARTITION BY s.cik, s.dimension_axis, s.dimension_member, s.concept 
    ORDER BY s.period_end
  ), 0) * 100 as growth_rate
FROM `sec-ai-466316.sec_data.segments` s;