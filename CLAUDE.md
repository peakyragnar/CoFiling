# SEC Filing Analysis System - Project Context for Claude

## Project Overview

This project builds an automated system to extract, parse, and analyze SEC financial filings for AI-powered financial analysis. The system achieves 100% capture of structured financial data including all segment breakdowns, which are critical for understanding company performance across different business lines, geographies, and asset categories.

## Primary Goals

1. **Complete Data Capture**: Extract 100% of financial data from SEC filings, including all segment dimensions
2. **AI-Ready Format**: Structure data for analysis by Gemini and other LLMs
3. **Cloud Integration**: Store in Google Cloud (GCS + BigQuery) for scalable analysis
4. **Automated Verification**: Ensure data completeness and correctness

## Current Architecture

### Data Pipeline Flow
```
CIK Input → SEC APIs → Parse XBRL → Merge Sources → Cloud Storage → AI Analysis
    ↓           ↓           ↓            ↓              ↓            ↓
Tesla CIK → Facts+Instance → Segments → JSON+PDF → GCS/BigQuery → Gemini
```

### Key Components

1. **SEC Data Sources**
   - Company Facts API: Summary data (616 concepts, but 0 segments)
   - XBRL Instance File: Complete data (2,006 facts, 477 with segments, 21 dimensions)
   - Filing HTML: Narrative text content

2. **PDF Supplements**
   - Earnings releases for additional context
   - Tables extracted with pdfplumber
   - Enriches SEC data with forward guidance

3. **Data Structure**
   ```json
   {
     "metadata": {"cik": "1318605", "entityName": "Tesla, Inc."},
     "structured": {
       "facts": {"Revenues": [...]},
       "segments": {
         "ProductOrServiceAxis": {
           "AutomotiveMember": [...],
           "EnergyGenerationMember": [...]
         }
       }
     },
     "text": {"full_filing": "...", "pdf_text": "..."}
   }
   ```

## Technical Implementation

### Main Script: `fetch_sec_facts.py`
- Fetches SEC data via official APIs (no scraping)
- Downloads XBRL instance for complete segment data
- Parses PDF supplements
- Merges data deterministically
- Uploads to Google Cloud
- Runs verification checks

### Key Functions
- `fetch_sec_facts()`: Gets Company Facts API data
- `fetch_xbrl_instance_direct()`: Gets complete XBRL with segments
- `parse_xbrl_instance_file()`: Extracts 21 segment dimensions
- `merge_sources()`: Combines SEC + PDF data
- `run_final_verification()`: Validates completeness

### Cloud Configuration
- **Project**: sec-ai-466316
- **GCS Bucket**: sec-ai-analyst
- **BigQuery Dataset**: sec_data (tables: facts, texts)

## Current Performance

- **Before**: 16.6% capture (Company Facts API only, 0 segments)
- **After**: 100% capture (XBRL instance, 21 segment dimensions, 477 segmented facts)
- **Verification**: 14 automated checks ensure completeness

## Important Context for Assistance

### When Working on This Project:

1. **Segments are Critical**
   - The Company Facts API has NO segment data
   - Must fetch XBRL instance file for segments
   - Segments break down revenue/costs by product, geography, etc.

2. **Data Completeness**
   - Primary HTML is only 16.6% of filing
   - XBRL instance has all structured data
   - Don't need full ZIP file - instance is sufficient

3. **Current Issues**
   - BigQuery insert errors for segment arrays (need flattening)
   - PDF parsing is basic (could use Gemini for better extraction)
   - No multi-company support yet (hardcoded for Tesla)

4. **Next Priorities**
   - Fix BigQuery segment insertion
   - Add multi-company support
   - Implement Gemini analysis layer
   - Create automated quarterly updates

### Best Practices

1. **Always verify segment capture** - This is the most important data
2. **Use official SEC APIs** - Never scrape, use data.sec.gov endpoints
3. **Test with verification** - Run `run_final_verification()` after changes
4. **Track data sources** - Tag each fact with its origin (sec_api, xbrl_instance, pdf)

## Common Commands

```bash
# Run the pipeline
python fetch_sec_facts.py

# Check segment capture
jq '.structured.segments | keys' formatted_sec_data.json

# Verify completeness
grep "ALL VERIFICATION CHECKS PASSED" output.log

# Test Gemini integration
python test_gemini.py
```

## File Structure

```
/CoFiling/
├── fetch_sec_facts.py      # Main pipeline script
├── test_gemini.py          # Gemini integration test
├── system_design.md        # Architecture documentation
├── CLAUDE.md              # This file
├── raw_sec_facts.json      # Raw API response
├── formatted_sec_data.json # Structured data
├── merged_sec_data.json    # Final merged output
└── tsla_q1_2025_earnings.pdf # Manual PDF supplement
```

## How Claude Can Best Help

1. **Debugging**: Check segment extraction, BigQuery errors
2. **Enhancement**: Add new data sources, improve parsing
3. **Analysis**: Create Gemini prompts for financial insights
4. **Scaling**: Multi-company support, batch processing
5. **Validation**: Ensure 100% data capture maintained

Remember: The goal is complete, accurate financial data ready for AI analysis. Segments are essential for meaningful insights.