import os
import re
import casparser
from pdfminer.high_level import extract_text
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import feedparser

app = FastAPI()

# Add CORS middleware so Base44 can communicate with your server securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "ArthKosh API is running smoothly!"}

@app.get("/news")
def get_news():
    try:
        # Fetch live market news from LiveMint RSS Feed
        feed = feedparser.parse("https://www.livemint.com/rss/markets")
        articles = []
        
        # Grab the top 10 most recent articles
        for entry in feed.entries[:10]:
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": getattr(entry, "published", "")
            })
            
        return {"status": "success", "articles": articles}
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch news: {str(e)}"}
@app.post("/upload-cas")
def parse_cas(password: str = Form(...), file: UploadFile = File(...)):
    try:
        # Securely save the uploaded PDF temporarily
        file_path = "temp_cas.pdf"
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        
        # Read the PDF (This returns the custom CASData object)
        parsed_data = casparser.read_cas_pdf(file_path, password)
        
        # FIX: Convert the CASData object into a standard dictionary safely
        if hasattr(parsed_data, "model_dump"):
            data_dict = parsed_data.model_dump()
        elif hasattr(parsed_data, "dict"):
            data_dict = parsed_data.dict()
        else:
            data_dict = parsed_data  # Fallback just in case
            
        total_value = 0.0
        
        # Strategy 1: Read from parsed schemes directly using our new dictionary
        for folio in data_dict.get("folios", []):
            for scheme in folio.get("schemes", []):
                val_dict = scheme.get("valuation", {})
                
                # Try getting direct value
                scheme_value = val_dict.get("value", 0)
                
                # Try calculating from NAV * Unit Balance
                if not scheme_value:
                    nav = val_dict.get("nav", 0)
                    balance = scheme.get("close_calculated", scheme.get("close", 0))
                    if nav and balance:
                        scheme_value = float(nav) * float(balance)
                        
                if scheme_value:
                    total_value += float(scheme_value)
        
        # Strategy 2: ULTIMATE FALLBACK (Scan raw text for KFintech Typos)
        if total_value == 0:
            raw_text = extract_text(file_path, password=password)
            # Find all instances of "Market Value ... INR [Value]"
            matches = re.findall(r"Market Value.*?INR\s*([0-9,]+\.[0-9]+)", raw_text, re.IGNORECASE)
            for match in matches:
                # Remove any commas (e.g. 1,500.00 -> 1500.00) and add to total
                clean_value = match.replace(",", "")
                total_value += float(clean_value)
                
        # Clean up: immediately delete the temporary file for security
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # If both strategies failed
        if total_value == 0:
             return {"status": "error", "message": "Could not find valuation in this CAS."}
             
        return {"status": "success", "portfolio_value": round(total_value, 2)}
        
    except Exception as e:
        # Clean up just in case something crashes
        if os.path.exists("temp_cas.pdf"):
            os.remove("temp_cas.pdf")
        return {"status": "error", "message": f"An error occurred: {str(e)}"}
