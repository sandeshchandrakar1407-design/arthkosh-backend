from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import casparser
import feedparser
import os

app = FastAPI()

# Allow your frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/news")
def get_news():
    try:
        # Fetching live Mutual Fund news from Mint
        feed = feedparser.parse("https://www.livemint.com/rss/money")
        news_list = []
        # Grab the top 5 latest articles
        for item in feed.entries[:5]: 
            news_list.append({
                "title": item.title,
                "date": item.published,
                "summary": "Click to read full coverage on this update."
            })
        return news_list
    except:
        return [{"title": "Live market data currently unavailable", "date": "Today", "summary": "Check connection."}]
# --- PASTE THIS NEW SECTION IN ITS PLACE ---
@app.post("/upload-cas")
def parse_cas(password: str = Form(...), file: UploadFile = File(...)):
    try:
        # Securely save the uploaded PDF temporarily
        file_path = "temp_cas.pdf"
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        
        # casparser cracks the password and reads the portfolio
        parsed_data = casparser.read_cas_pdf(file_path, password, output="dict")
        
        # Clean up: immediately delete the temporary file for security
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Calculate total valuation manually by reading the scheme market values
        total_value = 0.0
        
        for folio in parsed_data.get("folios", []):
            for scheme in folio.get("schemes", []):
                # Safely extract the market value found in the PDF
                val_dict = scheme.get("valuation", {})
                scheme_value = val_dict.get("value", 0)
                
                # Add to our running total
                if scheme_value:
                    total_value += float(scheme_value)
        
        # If extraction failed completely
        if total_value == 0:
             return {"status": "error", "message": "Could not find valuation in this CAS."}
             
        return {"status": "success", "portfolio_value": round(total_value, 2)}
        
    except Exception as e:
        # Clean up just in case something crashes
        if os.path.exists("temp_cas.pdf"):
            os.remove("temp_cas.pdf")
        return {"status": "error", "message": f"An error occurred: {str(e)}"}

        # Clean up just in case
        if os.path.exists("temp_cas.pdf"):
            os.remove("temp_cas.pdf")
        return {"status": "error", "message": "Incorrect password or invalid CAMS/KFintech CAS PDF."}
