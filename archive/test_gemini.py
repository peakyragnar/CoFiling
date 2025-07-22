import vertexai
from vertexai.generative_models import GenerativeModel

# Initialize Vertex AI
vertexai.init(project="sec-ai-466316", location="us-central1")

# Load Gemini model
model = GenerativeModel("gemini-2.5-pro")

# Test prompt (related to your project)
response = model.generate_content("Test: Briefly explain how Gemini can help analyze SEC filings.")
print(response.text)