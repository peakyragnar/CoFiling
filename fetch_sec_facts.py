import requests
import json
import pandas as pd
from bs4 import BeautifulSoup
import pdfplumber
import os
from google.cloud import storage, bigquery
import zipfile
import xml.etree.ElementTree as ET

headers = {'User-Agent': 'mic.b.cunningham@gmail.com'}

def fetch_sec_facts(cik):
    # Fetch Company Facts API for XBRL data (financials, segments)
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

def fetch_filing_index(cik, accession_number):
    """Fetch filing index to see ALL documents in a filing"""
    accession_clean = accession_number.replace('-', '')
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/index.json"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def analyze_filing_completeness(filing_index, captured_file):
    """Analyze what percentage of filing we're capturing"""
    total_size = 0
    captured_size = 0
    xbrl_files = []
    exhibits = []
    
    for item in filing_index['directory']['item']:
        size_str = item.get('size', '0')
        size = int(size_str) if size_str and size_str.isdigit() else 0
        total_size += size
        
        if item['name'] == captured_file:
            captured_size = size
        
        # Categorize files
        if item['name'].endswith(('.xml', '.xsd', '_cal.xml', '_def.xml', '_lab.xml', '_pre.xml')):
            xbrl_files.append(item['name'])
        elif item['name'].startswith('EX-'):
            exhibits.append(item['name'])
    
    completeness = (captured_size / total_size * 100) if total_size > 0 else 0
    
    print(f"\n📊 Completeness Analysis:")
    print(f"   - Capturing: {captured_size:,} bytes ({completeness:.1f}%)")
    print(f"   - Total filing: {total_size:,} bytes")
    print(f"   - Missing: {total_size - captured_size:,} bytes ({100-completeness:.1f}%)")
    
    if xbrl_files:
        print(f"\n⚠️  Missing {len(xbrl_files)} XBRL files (detailed financial data)")
    if exhibits:
        print(f"⚠️  Missing {len(exhibits)} exhibits (contracts, certifications)")
    
    return completeness

def parse_sec_facts(raw_data):
    # Extract structured facts and segments from raw JSON
    facts = raw_data.get('facts', {}).get('us-gaap', {})
    formatted = {"metadata": {"cik": raw_data['cik'], "entityName": raw_data['entityName']}, "structured": {"facts": {}, "segments": {}}}
    segment_count = 0

    for concept, data in facts.items():
        units = data.get('units', {})
        for unit, values in units.items():
            fact_list = []
            for v in values:
                # Get period - handle different period formats
                period = v.get('fy') or v.get('end') or v.get('instant') or v.get('start')
                value = v.get('val')
                
                if period and value is not None:
                    fact_list.append({"period": period, "value": value, "unit": unit})

                # Handle segments (dimensions) - fixed to use 'segment' not 'segments'
                if 'segment' in v:
                    segment_count += 1
                    for seg in v['segment']:
                        axis = seg.get('dimension', '')
                        member = seg.get('value', '')
                        if axis not in formatted["structured"]["segments"]:
                            formatted["structured"]["segments"][axis] = {}
                        if member not in formatted["structured"]["segments"][axis]:
                            formatted["structured"]["segments"][axis][member] = []
                        formatted["structured"]["segments"][axis][member].append({
                            "concept": concept,
                            "period": period,
                            "value": value,
                            "unit": unit
                        })
            
            if fact_list:
                formatted["structured"]["facts"][concept] = fact_list

    # Text extraction would come from full filings (next sub-step); stub for now
    formatted["text"] = {"mda": "Placeholder MD&A text from full filing"}
    
    print(f"✓ Parsed {len(facts)} concepts, {segment_count} segment entries")

    # Save formatted
    with open('formatted_sec_data.json', 'w') as f:
        json.dump(formatted, f, indent=4)
    print("Parsing successful! Formatted data saved to formatted_sec_data.json")
    return formatted

def validate_api_completeness(raw_data, formatted_data):
    """Validate completeness of API data capture"""
    print("\n🔍 API Data Validation:")
    
    # Check facts
    facts = raw_data.get('facts', {}).get('us-gaap', {})
    print(f"   - Concepts captured: {len(facts)}")
    
    # Check segments
    segments = formatted_data['structured']['segments']
    has_segments = len(segments) > 0
    print(f"   - Has segments: {'✓ Yes' if has_segments else '✗ No'}")
    
    if has_segments:
        print(f"   - Segment dimensions: {len(segments)}")
        for axis, members in list(segments.items())[:3]:  # Show first 3
            print(f"     • {axis}: {len(members)} members")
    
    # Check for common financial items
    common_items = ['Revenues', 'Assets', 'Liabilities', 'CashAndCashEquivalents']
    found_items = [item for item in common_items if item in facts]
    print(f"   - Common items found: {len(found_items)}/{len(common_items)}")
    
    # Overall assessment
    is_complete = len(facts) > 100 and has_segments
    print(f"\n{'✓' if is_complete else '✗'} API capture {'complete' if is_complete else 'incomplete'}")
    
    return is_complete

# Test with Tesla CIK
cik = '0001318605'  # TSLA
fetch_sec_facts(cik)

# Run parser on fetched data
with open('raw_sec_facts.json', 'r') as f:
    raw_data = json.load(f)
formatted = parse_sec_facts(raw_data)

# Validate API completeness
is_complete = validate_api_completeness(raw_data, formatted)
print(f"\n📊 Overall capture assessment: {'Complete' if is_complete else 'Incomplete'}")

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
    filings = submissions_data['filings']['recent']
    for i in range(len(filings['form'])):
        if filings['form'][i] == filing_type:
            accession = filings['accessionNumber'][i]
            accession_clean = accession.replace('-', '')
            report_date = filings['reportDate'][i]
            filename = filings['primaryDocument'][i]
            
            # Get filing index to analyze completeness
            filing_index = fetch_filing_index(submissions_data['cik'], accession)
            if filing_index:
                print(f"\n📁 Filing {accession} contains {len(filing_index['directory']['item'])} documents")
                
            url = f"https://www.sec.gov/Archives/edgar/data/{submissions_data['cik']}/{accession_clean}/{filename}"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'xml')  # Use xml parser
                text = ' '.join(soup.stripped_strings)  # Basic text extraction
                
                # Analyze completeness
                if filing_index:
                    completeness = analyze_filing_completeness(filing_index, filename)
                    print(f"\n💡 For 100% capture, download:")
                    print(f"   https://www.sec.gov/Archives/edgar/data/{submissions_data['cik']}/{accession_clean}/{accession}-xbrl.zip")
                
                return {"report_date": report_date, "text": text, "accession": accession}
            else:
                print(f"Error fetching filing: {response.status_code}")
    return None

def fetch_xbrl_instance_direct(cik, accession, report_date):
    """Fetch XBRL instance file directly"""
    accession_clean = accession.replace('-', '')
    
    # Try to construct instance filename from report date
    # report_date format: 2025-03-31, need: tsla-20250331
    date_part = report_date.replace('-', '')
    
    # Try different naming patterns
    patterns = [
        f"tsla-{date_part}_htm.xml",
        f"tsla-{date_part}.xml",
        f"{cik}-{date_part}_htm.xml"
    ]
    
    for pattern in patterns:
        instance_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/{pattern}"
        print(f"\n📦 Trying to fetch XBRL instance: {pattern}")
        response = requests.get(instance_url, headers=headers)
        
        if response.status_code == 200:
            instance_path = f"{accession}_instance.xml"
            with open(instance_path, 'wb') as f:
                f.write(response.content)
            print(f"✓ XBRL instance downloaded: {len(response.content):,} bytes")
            return instance_path
    
    print(f"✗ Could not fetch XBRL instance file")
    return None

def parse_xbrl_instance_file(instance_path):
    """Parse XBRL instance file for complete facts and segments"""
    try:
        tree = ET.parse(instance_path)
        root = tree.getroot()
        
        # Get all namespaces from the root element
        namespaces = dict([node for _, node in ET.iterparse(instance_path, events=['start-ns'])])
        if not namespaces:
            namespaces = {
                'xbrli': 'http://www.xbrl.org/2003/instance',
                'us-gaap': 'http://fasb.org/us-gaap/2024'
            }
        
        facts = {}
        segments = {}
        fact_count = 0
        segment_count = 0
        
        # Find all contexts with segments first
        contexts_with_segments = {}
        for context in root.findall('.//{http://www.xbrl.org/2003/instance}context'):
            context_id = context.get('id')
            segment = context.find('.//{http://www.xbrl.org/2003/instance}segment')
            if segment is not None:
                contexts_with_segments[context_id] = segment
        
        print(f"✓ Found {len(contexts_with_segments)} contexts with segments")
        
        # Parse all facts
        for elem in root.iter():
            if '}' in elem.tag and elem.text and elem.text.strip():
                namespace, concept = elem.tag.rsplit('}', 1)
                
                # Skip meta elements
                if concept in ['context', 'unit', 'schemaRef', 'xbrl', 'roleRef', 'arcroleRef']:
                    continue
                
                fact_count += 1
                context_ref = elem.get('contextRef', '')
                
                # Check if this fact has segment data
                if context_ref in contexts_with_segments:
                    segment_count += 1
                    segment = contexts_with_segments[context_ref]
                    
                    # Extract dimensions and members
                    for child in segment:
                        if 'explicitMember' in child.tag:
                            dimension = child.get('dimension', '').split(':')[-1]
                            member_text = child.text or ''
                            member = member_text.split(':')[-1] if member_text else ''
                            
                            if dimension and member:
                                if dimension not in segments:
                                    segments[dimension] = {}
                                if member not in segments[dimension]:
                                    segments[dimension][member] = []
                                
                                segments[dimension][member].append({
                                    "concept": concept,
                                    "value": elem.text.strip(),
                                    "context": context_ref
                                })
        
        print(f"✓ Parsed {fact_count} facts, {segment_count} with segments")
        print(f"✓ Found {len(segments)} segment dimensions")
        
        if segments:
            for dim, members in list(segments.items())[:2]:  # Show first 2 dimensions
                print(f"   • {dim}: {len(members)} members")
        
        return {"facts": facts, "segments": segments, "fact_count": fact_count}
        
    except Exception as e:
        print(f"✗ Error parsing XBRL instance: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def parse_xbrl_instance_from_zip(zip_path, accession):
    """Extract and parse XBRL instance file from ZIP for complete segment data"""
    extract_dir = f"{accession}_extracted"
    
    # Extract ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        file_list = zip_ref.namelist()
        print(f"✓ Extracted {len(file_list)} files from ZIP")
        print("📄 Files in ZIP:")
        for f in file_list:
            print(f"   - {f}")
    
    # Find XBRL instance file
    instance_file = None
    for file in file_list:
        if file.endswith('.xml') and ('instance' in file or '_htm' in file or file.startswith('tsla-')):
            instance_file = os.path.join(extract_dir, file)
            break
    
    if not instance_file:
        # Try alternative pattern - main XML that's not a linkbase
        for file in file_list:
            if file.endswith('.xml') and not any(x in file for x in ['_cal', '_def', '_lab', '_pre', '.xsd']):
                instance_file = os.path.join(extract_dir, file)
                break
    
    if not instance_file:
        print("✗ No XBRL instance file found in ZIP")
        return None
    
    print(f"✓ Found XBRL instance: {os.path.basename(instance_file)}")
    
    # Parse XBRL instance
    try:
        tree = ET.parse(instance_file)
        root = tree.getroot()
        
        # Extract namespace mappings
        namespaces = {
            'xbrli': 'http://www.xbrl.org/2003/instance',
            'us-gaap': 'http://fasb.org/us-gaap/2024',
            'dei': 'http://xbrl.sec.gov/dei/2024'
        }
        
        facts = {}
        segments = {}
        fact_count = 0
        segment_count = 0
        
        # Find all facts
        for elem in root.iter():
            if '}' in elem.tag:
                namespace, concept = elem.tag.rsplit('}', 1)
                
                # Skip non-fact elements
                if concept in ['context', 'unit', 'schemaRef', 'xbrl']:
                    continue
                
                if elem.text:
                    fact_count += 1
                    context_ref = elem.get('contextRef', '')
                    
                    # Look for segment information in context
                    context = root.find(f".//xbrli:context[@id='{context_ref}']", namespaces)
                    if context is not None:
                        segment_elem = context.find('.//xbrli:segment', namespaces)
                        if segment_elem is not None:
                            segment_count += 1
                            # Extract segment dimensions
                            for explicit_member in segment_elem.findall('.//*[@dimension]'):
                                dimension = explicit_member.get('dimension', '').split(':')[-1]
                                member = explicit_member.text.split(':')[-1] if explicit_member.text else ''
                                
                                if dimension not in segments:
                                    segments[dimension] = {}
                                if member not in segments[dimension]:
                                    segments[dimension][member] = []
                                
                                segments[dimension][member].append({
                                    "concept": concept,
                                    "value": elem.text,
                                    "context": context_ref
                                })
        
        print(f"✓ Parsed {fact_count} facts, {segment_count} with segments")
        print(f"✓ Found {len(segments)} segment dimensions")
        
        # Clean up extracted files
        import shutil
        shutil.rmtree(extract_dir)
        
        return {"facts": facts, "segments": segments, "fact_count": fact_count}
        
    except Exception as e:
        print(f"✗ Error parsing XBRL: {str(e)}")
        return None

# Run: Fetch submissions, get full filing text, add to formatted
submissions = fetch_sec_submissions(cik)
if submissions:
    full_filing = fetch_full_filing(submissions, '10-Q')  # Get recent 10-Q text
    if full_filing:
        formatted["text"]["full_filing"] = full_filing["text"]
        
        # Fetch XBRL instance directly for complete segment data
        accession = full_filing.get('accession')
        report_date = full_filing.get('report_date')
        if accession and report_date:
            instance_path = fetch_xbrl_instance_direct(submissions['cik'], accession, report_date)
            if instance_path:
                # Parse the instance file
                xbrl_data = parse_xbrl_instance_file(instance_path)
                if xbrl_data and xbrl_data['segments']:
                    # Merge XBRL segments with existing data
                    print("\n🔄 Merging XBRL segments with existing data...")
                    for dimension, members in xbrl_data['segments'].items():
                        if dimension not in formatted["structured"]["segments"]:
                            formatted["structured"]["segments"][dimension] = {}
                        formatted["structured"]["segments"][dimension].update(members)
                    print(f"✓ Added {len(xbrl_data['segments'])} segment dimensions from XBRL")
                
                # Clean up instance file
                os.remove(instance_path)
        
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