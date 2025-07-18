import requests
import json
import pandas as pd
from bs4 import BeautifulSoup
import pdfplumber
import os
from google.cloud import storage, bigquery

def fetch_sec_facts(cik):
    # Fetch Company Facts API for XBRL data (financials, segments)
    headers = {'User-Agent': 'mic.b.cunningham@gmail.com'}
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # Save to file for now
        with open('raw_sec_facts.json', 'w') as f:
            json.dump(data, f, indent=4)
        print("Fetch successful! Data saved to raw_sec_facts.json")
        return data
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def parse_sec_facts(raw_data):
    # Extract structured facts and segments from raw JSON
    facts = raw_data.get('facts', {}).get('us-gaap', {})
    formatted = {"metadata": {"cik": raw_data['cik'], "entityName": raw_data['entityName']}, "structured": {"facts": {}, "segments": {}}}

    for concept, data in facts.items():
        values = data.get('units', {}).get('USD', [])
        if values:
            formatted["structured"]["facts"][concept] = [{"period": v['fy'], "value": v['val']} for v in values if 'fy' in v and 'val' in v]  # Basic facts

        # Handle segments (dimensions)
        for v in values:
            if 'segments' in v:
                for seg in v['segments']:
                    axis = seg.get('dimension', '')
                    member = seg.get('value', '')
                    if axis not in formatted["structured"]["segments"]:
                        formatted["structured"]["segments"][axis] = {}
                    if member not in formatted["structured"]["segments"][axis]:
                        formatted["structured"]["segments"][axis][member] = []
                    formatted["structured"]["segments"][axis][member].append({"period": v['fy'], "value": v['val']})

    # Text extraction would come from full filings (next sub-step); stub for now
    formatted["text"] = {"mda": "Placeholder MD&A text from full filing"}

    # Save formatted
    with open('formatted_sec_data.json', 'w') as f:
        json.dump(formatted, f, indent=4)
    print("Parsing successful! Formatted data saved to formatted_sec_data.json")
    return formatted

# Test with Tesla CIK
cik = '0001318605'  # TSLA
fetch_sec_facts(cik)

# Run parser on fetched data
with open('raw_sec_facts.json', 'r') as f:
    raw_data = json.load(f)
formatted = parse_sec_facts(raw_data)

def fetch_sec_submissions(cik):
    # Fetch submissions for filing metadata and document URLs
    headers = {'User-Agent': 'mic.b.cunningham@gmail.com'}
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def fetch_full_filing(submissions_data, filing_type='10-Q', index=0):
    # Get URL for a recent filing and download HTML for text
    headers = {'User-Agent': 'mic.b.cunningham@gmail.com'}
    filings = submissions_data['filings']['recent']
    for i in range(len(filings['form'])):
        if filings['form'][i] == filing_type:
            accession = filings['accessionNumber'][i].replace('-', '')
            report_date = filings['reportDate'][i]
            filename = filings['primaryDocument'][i]
            url = f"https://www.sec.gov/Archives/edgar/data/{submissions_data['cik']}/{accession}/{filename}"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'xml')  # Use xml parser
                text = ' '.join(soup.stripped_strings)  # Basic text extraction
                return {"report_date": report_date, "text": text}
            else:
                print(f"Error fetching filing: {response.status_code}")
    return None

# Run: Fetch submissions, get full filing text, add to formatted
submissions = fetch_sec_submissions(cik)
if submissions:
    full_filing = fetch_full_filing(submissions, '10-Q')  # Get recent 10-Q text
    if full_filing:
        formatted["text"]["full_filing"] = full_filing["text"]
        with open('formatted_sec_data.json', 'w') as f:
            json.dump(formatted, f, indent=4)
        print("Full filing text added to formatted_sec_data.json")

def fetch_pdf_supplement(pdf_url, pdf_path='earnings_release.pdf'):
    headers = {'User-Agent': 'mic.b.cunningham@gmail.com'}
    response = requests.get(pdf_url, headers=headers)
    if response.status_code == 200:
        with open(pdf_path, 'wb') as f:
            f.write(response.content)
        print("PDF fetched and saved.")
        return pdf_path
    else:
        print(f"Error: {response.status_code}")
        return None

def parse_pdf_supplement(pdf_path):
    text = ""
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or "\n"
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    return {"text": text, "tables": tables}

def parse_pdf_earnings(pdf_path):
    text = ""
    tables = []
    segments = {}  # For extracted segment data
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or "\n"
            page_tables = page.extract_tables()
            if page_tables:
                for table in page_tables:
                    # Basic table to DF for segments (e.g., if table has 'Revenue' and 'Automotive')
                    df = pd.DataFrame(table[1:], columns=table[0])
                    if 'Revenue' in df.values or 'Segment' in df.values:
                        # Simple segment extraction (expand for more)
                        for row in df.itertuples():
                            if 'Automotive' in row or 'Energy' in row:
                                segments[row[1]] = row[2] if len(row) > 2 else "N/A"
                    tables.append(df.to_dict())  # Save all tables
    return {"text": text, "tables": tables, "segments": segments}

# Run for manual PDF
pdf_path = 'tsla_q1_2025_earnings.pdf'  # Your downloaded file
if os.path.exists(pdf_path):
    pdf_data = parse_pdf_earnings(pdf_path)
    formatted["supplements"] = {"earnings_release": pdf_data}
    with open('formatted_sec_data.json', 'w') as f:
        json.dump(formatted, f, indent=4)
    print("PDF parsed and added to formatted_sec_data.json")
    
    def merge_sources(sec_formatted, pdf_data):
        merged = sec_formatted.copy()
        merged["metadata"]["sources"] = ["sec_api", "pdf_earnings"]

        # Merge segments (priority: SEC, enrich with PDF)
        pdf_segments = pdf_data.get("segments", {})
        for axis, members in pdf_segments.items():
            if axis not in merged["structured"]["segments"]:
                merged["structured"]["segments"][axis] = {}
            for member, value in members.items():
                if member not in merged["structured"]["segments"][axis]:
                    merged["structured"]["segments"][axis][member] = {"value": value, "source": "pdf_earnings"}
                # Validation: If SEC has matching, check tolerance (e.g., ±5%)
                # Add logic if needed

        # Add PDF text/tables
        merged["text"]["pdf_text"] = pdf_data["text"]
        merged["structured"]["pdf_tables"] = pdf_data["tables"]

        with open('merged_sec_data.json', 'w') as f:
            json.dump(merged, f, indent=4)
        print("Merged data saved to merged_sec_data.json")
        return merged

    # Run after PDF parse
    merged_data = merge_sources(formatted, pdf_data)
    
    def upload_to_gcs(file_path, bucket_name='sec-ai-analyst'):
        project_id = 'sec-ai-466316'
        client = storage.Client(project=project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        blob.upload_from_filename(file_path)
        print(f"Uploaded {file_path} to GCS.")

    def insert_to_bigquery(merged):
        client = bigquery.Client()
        project_id = 'sec-ai-466316'
        dataset_id = 'sec_data'

        # Insert text to 'texts'
        texts_row = {
            "cik": merged["metadata"]["cik"],
            "date": "2025-03-31",  # From filing
            "source_type": "merged",
            "text_content": merged["text"].get("full_filing", "") + merged["text"].get("pdf_text", "")
        }
        texts_table = f"{project_id}.{dataset_id}.texts"
        errors = client.insert_rows_json(texts_table, [texts_row])
        if not errors:
            print("Text inserted to BigQuery.")

        # Insert facts/segments to 'facts' (flatten)
        facts_rows = []
        for concept, values in merged["structured"]["facts"].items():
            for v in values:
                row = {
                    "cik": merged["metadata"]["cik"],
                    "period": v["period"],
                    "concept": concept,
                    "value": v["value"],
                    "unit": "USD"  # Default unit
                }
                facts_rows.append(row)
        # Add segments as rows (concept = axis, value = member value)
        for axis, members in merged["structured"]["segments"].items():
            for member, data in members.items():
                # Handle both dict and direct value formats
                if isinstance(data, dict):
                    value = data.get("value", "N/A")
                    source = data.get("source", "unknown")
                else:
                    value = data
                    source = "unknown"
                    
                row = {
                    "cik": merged["metadata"]["cik"],
                    "period": "2025-03-31",  # Default period
                    "concept": f"{axis}_{member}",
                    "value": str(value),
                    "unit": "USD",
                    "dimension_axis": axis,
                    "dimension_member": member
                }
                facts_rows.append(row)
        facts_table = f"{project_id}.{dataset_id}.facts"
        errors = client.insert_rows_json(facts_table, facts_rows)
        if not errors:
            print("Facts/segments inserted to BigQuery.")
        else:
            print(f"BigQuery insert errors: {errors}")

    # Run after merging
    upload_to_gcs('merged_sec_data.json')
    insert_to_bigquery(merged_data)
else:
    print(f"PDF file {pdf_path} not found. Please download Tesla's Q1 2025 earnings PDF and save it as '{pdf_path}'")