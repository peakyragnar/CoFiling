#!/usr/bin/env python3
"""Run tests for SEC extraction validation"""
import subprocess
import sys
from pathlib import Path

def run_tests():
    """Run all tests and report results"""
    print("Running SEC Extraction Tests...")
    print("="*60)
    
    # Run unit tests
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_sec_extraction", "-v"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode

def test_with_existing_data():
    """Test using existing output data"""
    print("\nTesting with existing data files...")
    print("-"*60)
    
    output_dir = Path("output")
    test_cik = "0001318605"
    
    files_to_check = [
        f"raw_sec_facts_{test_cik}.json",
        f"formatted_sec_data_{test_cik}.json",
        f"validation_report_{test_cik}.json"
    ]
    
    print("\nChecking for output files:")
    all_exist = True
    for filename in files_to_check:
        filepath = output_dir / filename
        exists = filepath.exists()
        all_exist &= exists
        status = "✓" if exists else "✗"
        size = f"({filepath.stat().st_size:,} bytes)" if exists else ""
        print(f"  {status} {filename} {size}")
    
    if all_exist:
        print("\n✓ All required files exist. SEC extraction has been run successfully.")
        print("\nTo run the extraction again:")
        print("  python main.py --cik 1318605")
    else:
        print("\n✗ Some files are missing. Run the extraction first:")
        print("  python main.py --cik 1318605")
    
    return 0 if all_exist else 1

if __name__ == "__main__":
    # Run unit tests
    test_result = run_tests()
    
    # Check existing data
    data_result = test_with_existing_data()
    
    # Exit with error if any tests failed
    sys.exit(test_result or data_result)