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

@app.post("/upload-cas")
def parse_cas(password: str = Form(...), file: UploadFile = File(...)):
    try:
        # Securely save the uploaded PDF temporarily
        file_path = "temp_cas.pdf"
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        
        # casparser cracks the password and reads the portfolio value
        parsed_data = casparser.read_cas_pdf(file_path, password, output="dict")
        
        # Clean up: immediately delete the temporary file for security
        os.remove(file_path)
        
        # Extract the total valuation
        total_value = parsed_data.get("portfolio_valuation", 0) 
        
        # If extraction failed but didn't error out completely
        if total_value == 0:
             return {"status": "error", "message": "Could not find valuation in this CAS."}
             
        return {"status": "success", "portfolio_value": total_value}
        
    except Exception as e:
        # Clean up just in case
        if os.path.exists("temp_cas.pdf"):
            os.remove("temp_cas.pdf")
        return {"status": "error", "message": "Incorrect password or invalid CAMS/KFintech CAS PDF."}
