#!/usr/bin/env python3
"""
Batch process multiple companies' SEC filings
"""

import json
import subprocess
import logging
from datetime import datetime
from typing import List, Dict
import concurrent.futures
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Popular company CIKs for testing
COMPANY_LIST = [
    {"cik": "0001318605", "name": "Tesla"},
    {"cik": "0000320193", "name": "Apple"},
    {"cik": "0001652044", "name": "Alphabet"},
    {"cik": "0001018724", "name": "Amazon"},
    {"cik": "0000789019", "name": "Microsoft"},
    {"cik": "0001326801", "name": "Meta"},
    {"cik": "0001045810", "name": "NVIDIA"},
    {"cik": "0000034088", "name": "Exxon Mobil"},
    {"cik": "0000051143", "name": "IBM"},
    {"cik": "0000886982", "name": "Goldman Sachs"}
]

def process_company(company: Dict, filing_type: str = "10-Q") -> Dict:
    """Process a single company's filings"""
    start_time = time.time()
    cik = company['cik']
    name = company['name']
    
    logger.info(f"Processing {name} (CIK: {cik})")
    
    try:
        # Run the pipeline script
        cmd = [
            'python3', 
            'fetch_sec_facts_v2.py',
            '--cik', cik,
            '--filing-type', filing_type
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        success = result.returncode == 0
        duration = time.time() - start_time
        
        if success:
            logger.info(f"✓ {name} completed in {duration:.1f}s")
        else:
            logger.error(f"✗ {name} failed: {result.stderr}")
        
        return {
            "company": name,
            "cik": cik,
            "success": success,
            "duration": duration,
            "error": result.stderr if not success else None
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"✗ {name} timed out")
        return {
            "company": name,
            "cik": cik,
            "success": False,
            "duration": time.time() - start_time,
            "error": "Process timed out after 5 minutes"
        }
    except Exception as e:
        logger.error(f"✗ {name} error: {e}")
        return {
            "company": name,
            "cik": cik,
            "success": False,
            "duration": time.time() - start_time,
            "error": str(e)
        }

def batch_process(
    companies: List[Dict] = None,
    filing_type: str = "10-Q",
    max_workers: int = 3
) -> List[Dict]:
    """Process multiple companies in parallel"""
    
    if companies is None:
        companies = COMPANY_LIST
    
    logger.info(f"Starting batch processing for {len(companies)} companies")
    logger.info(f"Filing type: {filing_type}, Max workers: {max_workers}")
    
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        future_to_company = {
            executor.submit(process_company, company, filing_type): company
            for company in companies
        }
        
        # Process completed jobs
        for future in concurrent.futures.as_completed(future_to_company):
            result = future.result()
            results.append(result)
    
    # Summary statistics
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    total_duration = sum(r['duration'] for r in results)
    
    logger.info("\n" + "="*60)
    logger.info("BATCH PROCESSING SUMMARY")
    logger.info("="*60)
    logger.info(f"Total companies: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total time: {total_duration:.1f}s")
    logger.info(f"Average time per company: {total_duration/len(results):.1f}s")
    
    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "total_duration": total_duration
        },
        "results": results
    }
    
    with open('batch_processing_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info("\nReport saved to batch_processing_report.json")
    
    return results

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch process SEC filings')
    parser.add_argument(
        '--companies', 
        nargs='+', 
        help='List of CIKs to process (default: use built-in list)'
    )
    parser.add_argument(
        '--filing-type', 
        default='10-Q',
        choices=['10-K', '10-Q', '8-K'],
        help='Filing type to fetch'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='Number of parallel workers (default: 3)'
    )
    
    args = parser.parse_args()
    
    # Prepare company list
    if args.companies:
        companies = [{"cik": cik, "name": f"Company_{cik}"} for cik in args.companies]
    else:
        companies = COMPANY_LIST
    
    # Run batch processing
    batch_process(
        companies=companies,
        filing_type=args.filing_type,
        max_workers=args.workers
    )

if __name__ == "__main__":
    main()