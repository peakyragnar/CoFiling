#!/usr/bin/env python3
"""
Analyze Tesla earnings PDF to identify all segment tables and data points
This will help us build a better parser
"""

import pdfplumber
import json
import sys
from typing import List, Dict, Any
from pathlib import Path

def analyze_pdf_structure(pdf_path: str) -> Dict[str, Any]:
    """
    Analyze PDF to find all tables and key metrics
    """
    analysis = {
        "total_pages": 0,
        "tables_found": [],
        "key_metrics": [],
        "potential_segments": []
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        analysis["total_pages"] = len(pdf.pages)
        
        for page_num, page in enumerate(pdf.pages):
            # Extract text
            text = page.extract_text() or ""
            
            # Look for key metrics in text
            if "vehicle production" in text.lower():
                analysis["key_metrics"].append({
                    "page": page_num + 1,
                    "metric": "Vehicle Production",
                    "context": text[max(0, text.lower().find("vehicle production")-50):text.lower().find("vehicle production")+200]
                })
            
            if "vehicle deliveries" in text.lower():
                analysis["key_metrics"].append({
                    "page": page_num + 1,
                    "metric": "Vehicle Deliveries",
                    "context": text[max(0, text.lower().find("vehicle deliveries")-50):text.lower().find("vehicle deliveries")+200]
                })
                
            if "energy storage" in text.lower() or "gwh" in text.lower():
                analysis["key_metrics"].append({
                    "page": page_num + 1,
                    "metric": "Energy Storage",
                    "context": text[max(0, text.lower().find("energy storage")-50):text.lower().find("energy storage")+200]
                })
            
            # Extract tables
            tables = page.extract_tables()
            if tables:
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue
                    
                    # Analyze table structure
                    table_info = {
                        "page": page_num + 1,
                        "table_index": table_idx,
                        "rows": len(table),
                        "cols": len(table[0]) if table else 0,
                        "headers": table[0] if table else [],
                        "sample_rows": table[:3] if len(table) > 3 else table
                    }
                    
                    # Check if this might be a segment table
                    table_text = str(table).lower()
                    if any(keyword in table_text for keyword in [
                        "automotive", "energy", "services", "revenue", 
                        "gross profit", "model", "deliveries", "production",
                        "united states", "china", "gwh", "mwh"
                    ]):
                        table_info["likely_segment_table"] = True
                        analysis["potential_segments"].append(table_info)
                    
                    analysis["tables_found"].append(table_info)
    
    return analysis

def identify_target_tables(analysis: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    Identify which tables contain the data we need
    """
    targets = {
        "financial_summary": [],
        "vehicle_metrics": [],
        "energy_metrics": [],
        "geographic_segments": [],
        "product_segments": []
    }
    
    for table in analysis["tables_found"]:
        headers_str = " ".join(str(h).lower() for h in table.get("headers", []))
        sample_str = str(table.get("sample_rows", [])).lower()
        
        # Financial summary table
        if "revenue" in headers_str and ("gross profit" in headers_str or "operating" in headers_str):
            targets["financial_summary"].append(table)
        
        # Vehicle metrics
        if ("production" in sample_str or "deliveries" in sample_str) and "model" in sample_str:
            targets["vehicle_metrics"].append(table)
        
        # Energy metrics
        if ("gwh" in sample_str or "mwh" in sample_str) and "storage" in sample_str:
            targets["energy_metrics"].append(table)
        
        # Geographic segments
        if any(region in sample_str for region in ["united states", "china", "europe", "other"]):
            targets["geographic_segments"].append(table)
        
        # Product segments
        if "automotive" in sample_str and "energy" in sample_str and "services" in sample_str:
            targets["product_segments"].append(table)
    
    return targets

def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_analyzer.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    print(f"🔍 Analyzing PDF: {Path(pdf_path).name}")
    print("=" * 60)
    
    # Analyze PDF structure
    analysis = analyze_pdf_structure(pdf_path)
    
    print(f"\n📄 PDF Overview:")
    print(f"- Total pages: {analysis['total_pages']}")
    print(f"- Tables found: {len(analysis['tables_found'])}")
    print(f"- Key metrics found: {len(analysis['key_metrics'])}")
    print(f"- Potential segment tables: {len(analysis['potential_segments'])}")
    
    # Identify target tables
    targets = identify_target_tables(analysis)
    
    print(f"\n🎯 Target Tables Identified:")
    for category, tables in targets.items():
        print(f"- {category}: {len(tables)} table(s)")
        if tables:
            for table in tables[:1]:  # Show first table details
                print(f"  Page {table['page']}, {table['rows']}x{table['cols']} table")
                print(f"  Headers: {table['headers']}")
    
    # Show key metrics
    print(f"\n📊 Key Metrics Found:")
    for metric in analysis["key_metrics"][:5]:
        print(f"- {metric['metric']} (Page {metric['page']})")
        print(f"  Context: {metric['context'][:100]}...")
    
    # Save analysis
    with open("tesla_pdf_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2, default=str)
    
    print(f"\n💾 Full analysis saved to tesla_pdf_analysis.json")
    
    # Show what we need to extract
    print(f"\n🎯 Data Points We Need to Extract:")
    print("1. Vehicle Production & Deliveries:")
    print("   - Model S/X numbers")
    print("   - Model 3/Y numbers")
    print("   - Total production vs deliveries")
    print("\n2. Energy Metrics:")
    print("   - Energy storage deployed (GWh)")
    print("   - Solar deployed (MW)")
    print("\n3. Financial Segments:")
    print("   - Automotive revenue")
    print("   - Energy generation and storage revenue")
    print("   - Services and other revenue")
    print("\n4. Geographic Breakdown:")
    print("   - US revenue")
    print("   - China revenue")
    print("   - Other regions revenue")


if __name__ == "__main__":
    main()
    print("   - Other markets revenue")
    print("\n5. Margins:")
    print("   - Automotive gross margin")
    print("   - Total gross margin")
    print("   - Operating margin")

if __name__ == "__main__":
    main()