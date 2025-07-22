"""SEC API client for fetching company facts and filing data"""
import requests
import json
from typing import Dict, Optional, Any

class SECFetcher:
    """Client for fetching data from SEC EDGAR APIs"""
    
    def __init__(self, user_agent: str = "mic.b.cunningham@gmail.com"):
        self.headers = {'User-Agent': user_agent}
        self.base_url = "https://data.sec.gov/api/xbrl"
        
    def fetch_company_facts(self, cik: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company facts from SEC XBRL API
        
        Args:
            cik: Central Index Key for the company (e.g., "1318605" for Tesla)
            
        Returns:
            Dictionary containing company facts or None if error
        """
        url = f"{self.base_url}/companyfacts/CIK{cik.zfill(10)}.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching SEC facts: {e}")
            return None
            
    def fetch_filing_index(self, cik: str, accession_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetch filing index to see all documents in a filing
        
        Args:
            cik: Central Index Key
            accession_number: SEC accession number (e.g., "0001318605-24-000123")
            
        Returns:
            Filing index data or None if error
        """
        accession_clean = accession_number.replace('-', '')
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/index.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching filing index: {e}")
            return None