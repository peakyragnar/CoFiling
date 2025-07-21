# SEC AI Analyst System Design

## Overview
This document outlines the design for an AI-powered public company analyst system focused on extracting, parsing, formatting, storing, and analyzing data from SEC filings and PDF supplements (press releases, presentations). The system is built for determinism, completeness, and AI optimization (e.g., for Gemini via Vertex AI), with uploads to Google Cloud Storage (GCS) and BigQuery. It uses a hybrid approach:
- **SEC Data**: Primarily from official APIs for structured XBRL (facts, segments), with optional ZIP downloads for full filings if API is insufficient (e.g., for complete XBRL instance, exhibits).
- **PDF Supplements**: Fetched from company IR sites and parsed to enrich data (e.g., detailed segments not in XBRL).

The system runs automated checks for completeness/accuracy at key stages. Focus starts with verifying SEC data, then integrates PDFs and merging.

Key Goals:
- 100% deterministic output (same input = same result).
- Robust verification (e.g., compare against expected concepts, validate totals).
- Scalable for multiple companies/quarters.
- AI as analyst (agentic searches for trends, estimates).
- Storage in Google Cloud for queryability.

Tech Stack:
- Python for scripting (requests, pdfplumber, BeautifulSoup, pandas, Arelle for XBRL).
- Google Cloud: GCS (files/JSON), BigQuery (structured/text for queries), Vertex AI (Gemini).
- Tools: web_search/browse_page for dynamic PDF URLs.

Assumptions:
- Start with one company (e.g., Tesla CIK 1318605).
- Free tier sufficient initially; monitor costs.

## High-Level Architecture
Pipeline: Input → Fetch → Parse → Format/Merge → Verify → Store → AI Processing → Output/Analysis.

- **Fetch**: API for SEC summary; optional ZIP for full; dynamic for PDFs.
- **Parse**: XBRL/HTML for SEC; AI/pdfplumber for PDFs.
- **Merge**: Rule-based to combine (SEC primary, PDF enriches).
- **Verify**: Automated checks (e.g., concept presence, value matching).
- **Store**: GCS for raw/formatted, BigQuery for queryable.
- **AI**: Gemini for extraction/analysis/agentic queries.
- **Output**: JSON/Sheets for models; responses for queries (e.g., "inventory trends").

Data Flow Diagram (Text-Based):
```
Input (CIK, date) --> Fetch (API/ZIP + PDF URLs) --> Parse (XBRL/Text/Tables) --> Merge (Rules) --> Verify (Checks) --> Store (GCS/BigQuery) --> AI (Gemini Agentic) --> Output (JSON/Sheets/Responses)
```

## Detailed Module Design
1. **Input Handler**:
   - Accepts: CIK (e.g., '1318605'), filing types (10-K/Q), date range, IR URLs (or search queries for PDFs).
   - Output: Query params.
   - Determinism: Fixed resolution (e.g., CIK lookup via API).

2. **Fetcher Module**:
   - **SEC Data**:
     - Primary: Company Facts API for XBRL summary (facts/segments).
     - Optional Full: Submissions API for metadata, then ZIP download (e.g., /Archives/edgar/data/{cik}/{accession}-filing.zip) for complete package if API incomplete.
     - Why ZIP? For 100% (exhibits, full XBRL instance)—trigger if verification shows gaps.
   - **PDF Supplements**: Use web_search/browse_page to find URLs (e.g., "Tesla Q1 2025 earnings PDF"), then requests to download.
   - Determinism: Cache with timestamps; User-Agent header.
   - Tech: requests, zipfile for unzip.

3. **Parser Module**:
   - **SEC**: 
     - XBRL (from API or ZIP instance.xml): Arelle/pandas for facts/segments (fix to handle 'segment' arrays).
     - Text: BeautifulSoup for HTML sections (e.g., MD&A from 10-Q).
   - **PDFs**: pdfplumber for text/tables; Gemini multimodal if complex (prompt: "Extract segments/tables as JSON").
   - Output: Raw extracts (facts list, segments dict, text string).

4. **Format/Merge Module**:
   - Format to unified JSON (nested for segments, source tags).
   - Merge Rules (deterministic):
     - Priority: SEC for official; PDF if more detailed/matches ±5%.
     - Enrichment: Append PDF extras as "supplemental".
     - Validation: Check totals match; flag discrepancies.
   - Tech: Custom function with if-else rules.

5. **Verification Module**:
   - Automated Checks: After fetch/parse, validate (e.g., count concepts, check for 'segment' keys, compare values to known totals from PDF).
   - Completeness: % of expected concepts (e.g., Revenues, NetIncomeLoss); log missing.
   - Accuracy: Cross-check sums (e.g., segment totals = total revenue).
   - If gaps (e.g., <90%), trigger ZIP fetch.
   - Tech: Integrated in script (print logs or raise errors).

6. **Storage Module**:
   - Raw ZIP/PDFs/HTML: GCS (e.g., gs://bucket/raw/{cik}/{date}/).
   - Formatted/Merged JSON: GCS (gs://bucket/formatted/{cik}/merged.json).
   - Parsed Data: BigQuery (texts for narratives, facts for structured/segments).
   - Tech: google-cloud-storage/bigquery libraries.

7. **AI Processing Module**:
   - Post-Processing: Gemini on merged JSON (prompt: "Extract all segments as structured dict").
   - Agentic Search: For queries (e.g., "inventory trends"), agents plan/retrieve from BigQuery, analyze.
   - Tech: Vertex AI API.

8. **Output/Analysis**:
   - JSON/Sheets for models (e.g., trends as CSV).
   - Responses for queries (e.g., "Inventory up 15% YoY per segments").

## Implementation Plan
- **Phase 1: Setup** (Complete: GCS/BigQuery/Vertex AI).
- **Phase 2: Fetch/Parse SEC** (Current: API working; add ZIP if needed via rules).
- **Phase 3: PDF Integration** (Next: Dynamic URL fetch, parse, merge).
- **Phase 4: Verification/Storage** (Automated checks, upload to Cloud).
- **Phase 5: AI/Testing** (Gemini for extraction, agentic queries).

We're not "jumping"—focus on verifying SEC first (run validation code), then PDFs. ZIP is optional (trigger if API incomplete)—your understanding is correct, but we can minimize it. Ready for the validation code to run on your raw JSON?