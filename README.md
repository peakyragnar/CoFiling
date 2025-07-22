# SEC Filing Analysis System

A generic system for extracting and analyzing financial data from SEC filings and earnings reports, with AI-powered financial model generation.

## Features

- **SEC Data Extraction**: Fetches comprehensive financial data from SEC's Company Facts API
- **Generic PDF Parsing**: Extracts financial data from any company's earnings report PDF using AI
- **Intelligent Document Analysis**: Automatically identifies company, period, and business model
- **AI-Powered Extraction**: Uses Google's Gemini Vision to extract complex financial data
- **Data Validation**: Comprehensive validation framework to ensure data quality
- **Financial Model Generation**: (Coming soon) Generate financial projections using merged data

## Quick Start

### Prerequisites

- Python 3.8+
- Google Cloud API key (for Gemini Vision)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/CoFiling.git
cd CoFiling

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Basic Usage

```bash
# Extract SEC data and analyze earnings report
python main.py --cik 1318605 --pdf TSLA-Q1-2025-Update.pdf

# Extract only SEC data
python main.py --cik 1318605

# Specify output directory
python main.py --cik 1318605 --pdf earnings.pdf --output-dir results/
```

## Output

The system generates several JSON files:

- `raw_sec_facts_{cik}.json` - Raw SEC data
- `formatted_sec_data_{cik}.json` - Structured SEC data
- `earnings_data_{cik}.json` - Extracted PDF data
- `validation_report_{cik}.json` - SEC data validation
- `pdf_validation_report_{cik}.json` - PDF extraction validation

## Architecture

```
main.py
├── SEC Data Pipeline
│   ├── SECFetcher         # Fetches data from SEC EDGAR API
│   ├── XBRLParser         # Parses XBRL/Company Facts data
│   └── SECValidator       # Validates SEC data completeness
│
└── PDF Pipeline (Generic)
    ├── DocumentAnalyzer   # Analyzes document structure
    ├── SchemaGenerator    # Creates dynamic extraction schemas
    ├── GenericEarningsParser  # Orchestrates extraction
    │   └── GeminiClient   # AI-powered data extraction
    └── GenericPDFValidator    # Validates extracted data
```

## Recent Improvements

### Generic System (No Hardcoding)
- Automatically detects company name from documents
- Adapts to any company's report structure
- No predefined expectations or templates

### AI-Powered Extraction
- Uses Gemini Vision for accurate data extraction
- Handles complex tables and financial statements
- Extracts time series data across multiple periods

### Example Output
From Tesla Q1 2025 earnings:
- Total Revenue: $19,335M
- Automotive Revenue: $13,967M
- Energy Revenue: $2,730M
- Gross Margin: 16.3%
- Operating Margin: 2.1%

## Project Status

✅ **Completed**:
- SEC data fetching and parsing
- Generic PDF analysis and extraction
- Company identification
- Basic financial data extraction
- Validation frameworks

🚧 **In Progress**:
- Performance optimization for large PDFs
- SEC segment data extraction fixes

📋 **Planned**:
- AI-generated financial models
- Two-stage processing (understand then extract)
- Support for batch processing
- Enhanced time series analysis

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.