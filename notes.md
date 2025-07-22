7. How to Verify It's Working

  # Method 1: Run full extraction
  python main.py --cik 1318605

  # Method 2: Run unit tests
  python run_tests.py

  # Method 3: Check validation report
  cat output/validation_report_1318605.json | jq '.is_complete, .completeness_score'