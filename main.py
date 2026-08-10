import os
import re
import json
import casparser
from pdfminer.high_level import extract_text
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import google.generativeai as genai

# Configure the AI Agent using the secure Render environment variable
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... [Keep your existing /news endpoint here] ...

@app.post("/upload-cas")
def parse_cas(password: str = Form(...), file: UploadFile = File(...)):
    try:
        file_path = "temp_cas.pdf"
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        
        # --- PHASE 1: Standard Extraction ---
        parsed_data = casparser.read_cas_pdf(file_path, password)
        
        if hasattr(parsed_data, "model_dump"):
            data_dict = parsed_data.model_dump()
        elif hasattr(parsed_data, "dict"):
            data_dict = parsed_data.dict()
        else:
            data_dict = parsed_data
            
        total_value = 0.0
        
        for folio in data_dict.get("folios", []):
            for scheme in folio.get("schemes", []):
                val_dict = scheme.get("valuation", {})
                scheme_value = val_dict.get("value", 0)
                if scheme_value:
                    total_value += float(scheme_value)
        
        # --- PHASE 2: AI EXTRACTION FALLBACK ---
        if total_value == 0:
            # 1. Crack password and get all raw text
            raw_text = extract_text(file_path, password=password)
            
            # 2. Spin up the AI model
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 3. The strict prompt
            prompt = f"""
            You are an expert financial data extractor. 
            Analyze the following text extracted from a mutual fund Consolidated Account Statement (CAS).
            Find the grand total 'Market Value' or 'Portfolio Valuation' of all holdings combined.
            Return ONLY a valid JSON object in this exact format, with no markdown formatting, backticks, or extra text:
            {{"portfolio_value": 2567.18}}
            
            RAW CAS TEXT:
            {raw_text}
            """
            
            # 4. Ask the AI and parse the response
            response = model.generate_content(prompt)
            ai_data = json.loads(response.text.strip())
            total_value = float(ai_data.get("portfolio_value", 0))

        if os.path.exists(file_path):
            os.remove(file_path)
        
        if total_value == 0:
             return {"status": "error", "message": "Even our AI could not find the valuation in this CAS."}
             
        return {"status": "success", "portfolio_value": round(total_value, 2)}
        
    except Exception as e:
        if os.path.exists("temp_cas.pdf"):
            os.remove("temp_cas.pdf")
        return {"status": "error", "message": f"An error occurred: {str(e)}"}
