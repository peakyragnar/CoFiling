#!/usr/bin/env python3
"""
Debug Gemini response to understand format issues
"""
import google.generativeai as genai
import os
from pdf2image import convert_from_path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.environ.get('GOOGLE_API_KEY')
print(f"API Key loaded: {'Yes' if api_key else 'No'}")
print(f"API Key length: {len(api_key) if api_key else 0}")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Try multiple pages to find one with data
pdf_path = "TSLA-Q1-2025-Update.pdf"
print("Loading PDF pages...")

# Test pages 3-6 (likely financial summary pages)
for page_num in [3, 4, 5, 6]:
    print(f"\n--- Testing page {page_num} ---")
    images = convert_from_path(pdf_path, dpi=150, first_page=page_num, last_page=page_num)

    if not images:
        print(f"Failed to load page {page_num}")
        continue
    
    # More structured prompt
    prompt = """
    Extract financial data from this earnings report page.
    
    Return a JSON object with this structure:
    {
        "revenue": {
            "total": "value with unit like 19335M",
            "automotive": "value if found",
            "energy": "value if found"
        },
        "margins": {
            "gross": "percentage like 16.3%",
            "operating": "percentage if found"
        }
    }
    
    IMPORTANT: Return ONLY the JSON object, no other text.
    """
    
    # Skip prompt printing for brevity
    
    try:
        response = model.generate_content([prompt, images[0]])
        print(f"Response preview: {response.text[:100]}...")
        
        # Try to find JSON
        text = response.text
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = text[json_start:json_end]
            import json
            try:
                data = json.loads(json_str)
                # Check if we got actual data
                has_revenue = any(v for v in data.get('revenue', {}).values() if v and v != 'null')
                has_margins = any(v for v in data.get('margins', {}).values() if v and v != 'null')
                
                if has_revenue or has_margins:
                    print(f"✅ Found data! Revenue: {data.get('revenue', {})}, Margins: {data.get('margins', {})}")
                else:
                    print("❌ JSON returned but all values are null")
            except:
                print(f"Failed to parse JSON: {json_str[:50]}...")
        else:
            print("❌ No JSON structure found in response")
            
    except Exception as e:
        print(f"Error: {e}")
print("\nTest complete.")