#!/usr/bin/env python3
"""Run PDF analyzer on Tesla earnings report"""
import subprocess
import sys

# Run the PDF analyzer
result = subprocess.run([
    sys.executable, 
    "src/extraction/pdf_analyzer.py",
    "TSLA-Q1-2025-Update.pdf"
], capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print("Errors:", result.stderr)