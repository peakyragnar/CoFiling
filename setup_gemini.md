# Setting Up Gemini API

## Getting Your API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy your API key

## Setting the Environment Variable

### macOS/Linux:
```bash
export GOOGLE_API_KEY='your-api-key-here'
```

### Or add to your shell profile (~/.zshrc or ~/.bashrc):
```bash
echo "export GOOGLE_API_KEY='your-api-key-here'" >> ~/.zshrc
source ~/.zshrc
```

### Windows:
```cmd
set GOOGLE_API_KEY=your-api-key-here
```

## Testing the Parser

Once your API key is set:

```bash
python test_gemini_parser.py
```

## What Gemini Adds

The Gemini-enhanced parser can:
1. **Read charts and graphs** - Extract data from bar charts, pie charts, etc.
2. **Process infographics** - Get numbers from visual presentations
3. **Handle complex layouts** - Parse presentation-style PDFs
4. **Extract all segments** - Complete data including:
   - Energy storage (4.1 GWh not just 1.0)
   - Revenue by segment from charts
   - Geographic splits from pie charts
   - Margins from visual dashboards

## Security Note

Never commit your API key to git! Add to .gitignore:
```
.env
*.env
```

Store keys in environment variables or secure key management systems.