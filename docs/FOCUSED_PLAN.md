# SEC + Earnings → Gemini Financial Model System

## Current Focus: Build Core Pipeline First

### What We're Building
A system that:
1. Fetches SEC filings (10-K/10-Q) via EDGAR API
2. **Extracts segment data from earnings PDFs** (critical differentiator)
3. Merges SEC + earnings data deterministically
4. Feeds to Gemini to generate financial models
5. Outputs structured JSON financial models

### What We're NOT Building (Yet)
- Cloud deployment
- Google Sheets UI
- Multi-company batch processing
- Real-time updates

## Implementation Phases

### Phase 1: Perfect the Data Pipeline (Current)
**Goal**: Reliably extract ALL data, especially PDF segments

#### 1. Fix PDF Extraction (Week 1)
**Current State**: Basic table extraction in `fetch_sec_facts.py`
**Needed**: Smart extraction of:
- Vehicle delivery numbers by model (Model 3/Y, Model S/X)
- Energy deployment (GWh for storage, MW for solar)
- Regional revenue breakdowns (US, China, Other)
- Automotive vs Energy vs Services split
- Gross margins by segment

**Test Case**: Tesla Q1 2025 PDF (`tsla_q1_2025_earnings.pdf`)

#### 2. Build Deterministic Merger (Week 1)
```python
# Example merge rules
merge_rules = {
    "revenue": {
        "primary": "sec_xbrl",
        "validate_against": "pdf_earnings",
        "tolerance": 0.05  # 5%
    },
    "vehicle_deliveries": {
        "primary": "pdf_earnings",  # Only in PDF
        "required": True
    },
    "segment_revenue": {
        "primary": "pdf_earnings",  # More detailed
        "enrich_with": "sec_xbrl"
    }
}
```

#### 3. Create Validation Framework (Week 2)
- Segment totals = reported totals
- No missing critical metrics
- Source attribution clear
- Reproducible results

### Phase 2: Gemini Integration
**Goal**: Generate deterministic financial models

#### 1. Design Model Schema (Week 2)
```json
{
  "company": "Tesla, Inc.",
  "period": "Q1 2025",
  "financial_model": {
    "historicals": {
      "income_statement": [...],
      "balance_sheet": [...],
      "cash_flow": [...],
      "segments": {
        "by_product": [...],
        "by_geography": [...]
      }
    },
    "projections": {
      "assumptions": {
        "revenue_growth": "based_on_segment_trends",
        "margin_expansion": "based_on_scale"
      },
      "income_statement_5yr": [...],
      "dcf_valuation": {...}
    },
    "metrics": {
      "ratios": {...},
      "sensitivity": {...}
    }
  }
}
```

#### 2. Build Prompt Engineering (Week 3)
- Structured output mode
- Temperature = 0
- Schema enforcement
- Chain-of-thought for calculations

#### 3. Test & Iterate (Week 3)
- Run on Tesla data
- Verify reproducibility (3 runs = identical output)
- Validate calculations
- Compare to analyst models

## Success Criteria
- [ ] Extract 100% of segment data from earnings PDFs
- [ ] SEC + PDF data merge with 0 conflicts
- [ ] Gemini outputs identical models for same input
- [ ] Complete model generation in <2 minutes
- [ ] Model calculations are verifiable

## Current State (Honest Assessment)

### ✅ What Works:
- SEC data fetching (Company Facts API)
- XBRL parsing (2,006 facts extracted)
- Basic PDF text extraction
- JSON output structure

### ❌ Needs Work:
- **PDF segment extraction**: Currently extracts text but misses structured tables
- **Smart table detection**: Can't identify "Automotive Revenue" vs random tables
- **Deterministic merger**: Basic concatenation, no validation
- **Gemini integration**: Not started
- **Validation framework**: No automated checks

### 🔧 Technical Debt:
- Multiple similar scripts (consolidate)
- No proper error handling
- No logging framework
- No unit tests

## Next Immediate Steps

### Step 1: Analyze Tesla PDF Structure
```python
# What we need to find:
tables_to_extract = {
    "financial_summary": ["Revenue", "Gross Profit", "Operating Income"],
    "vehicle_metrics": ["Production", "Deliveries", "Model 3/Y", "Model S/X"],
    "energy_metrics": ["Solar Deployed", "Storage Deployed", "GWh"],
    "segment_breakdown": ["Automotive", "Energy", "Services", "by Geography"]
}
```

### Step 2: Build Smart PDF Parser
- Use table headers to identify relevant tables
- Extract with proper column/row alignment
- Handle merged cells and subtotals
- Output structured data, not just text

### Step 3: Create Merge Rules Engine
- Define precedence (SEC vs PDF)
- Implement validation (totals match)
- Handle conflicts gracefully
- Maintain audit trail

### Step 4: Test End-to-End
- Input: CIK + PDF path
- Output: Complete structured data
- Verify: All segments captured

## Repository Structure (Target)
```
/CoFiling/
├── docs/
│   ├── FOCUSED_PLAN.md          # This document
│   ├── high_level_design.md     # Reference architecture
│   └── CLAUDE.md                # Updated implementation notes
├── src/
│   ├── ingestion/
│   │   ├── sec_fetcher.py       # SEC API client
│   │   └── pdf_fetcher.py       # PDF downloader
│   ├── extraction/
│   │   ├── xbrl_parser.py       # XBRL/XML parser
│   │   └── earnings_parser.py   # Smart PDF parser
│   ├── merger/
│   │   └── data_merger.py       # Deterministic merger
│   ├── validation/
│   │   └── validator.py         # Data validation
│   └── ai/
│       └── gemini_client.py     # Financial model generator
├── tests/
│   └── test_data/
│       └── tsla_q1_2025_earnings.pdf
└── output/
    └── tesla_complete_data.json

## Timeline
- **Week 1**: Data pipeline (extraction + merger)
- **Week 2**: Validation + Gemini schema
- **Week 3**: Gemini integration + testing
- **Week 4**: Polish + documentation

## Definition of Done
When we can run:
```bash
python main.py --cik 1318605 --pdf tsla_q1_2025_earnings.pdf
```

And get:
1. Complete SEC + earnings data (100% segments)
2. Validated merged dataset
3. Gemini-generated financial model
4. Reproducible results