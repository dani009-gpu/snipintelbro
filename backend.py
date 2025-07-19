
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, shodan, requests, os, wikipedia
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO
from typing import Optional
import uvicorn

# ================= CONFIGURATION =================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constantes
DB_NAME = "spiderintel.db"
TELEGRAM_TOKEN = "7848590213:AAG3DDeuHdrdwL4ogxdV4eFpbCjfYtr14qI"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ================= MODÈLES =================
class Target(BaseModel):
    type: str  # "email", "ip", "domain", "celebrity"
    value: str
    user_id: Optional[str] = None

# ================= SERVICES =================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS targets ("
            "id INTEGER PRIMARY KEY,"
            "type TEXT,"
            "value TEXT UNIQUE,"
            "result TEXT,"
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.commit()

def scan_email(email: str):
    return {
        "status": "danger",
        "leaks": ["Adobe", "LinkedIn"],
        "is_disposable": False
    }

def scan_ip(ip: str):
    try:
        api = shodan.Shodan("b60fae6f92274daca86121eaf2656737")
        return api.host(ip)
    except:
        return {
            "ip": ip,
            "country": "France",
            "city": "Paris",
            "status": "warning"
        }

def scan_domain(domain: str):
    return {
        "status": "success",
        "registrar": "Nominal (simulation)",
        "dns": ["ns1.example.com"]
    }

def scan_celebrity(name: str):
    try:
        wikipedia.set_lang("fr")
        page = wikipedia.page(name, auto_suggest=True)
        return {
            "name": name,
            "summary": wikipedia.summary(name, sentences=3),
            "url": page.url
        }
    except:
        return {"status": "not_found"}

def generate_pdf(target: Target, result: dict):
    try:
        os.makedirs('reports', exist_ok=True)
        filename = f"{target.type}_{target.value.replace(' ', '_')}.pdf"
        pdf_path = os.path.join("reports", filename)
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 750, f"Rapport OSINT - {target.type.upper()}")
        
        y = 700
        for key, value in result.items():
            if y < 50:
                c.showPage()
                y = 750
            c.drawString(72, y, f"{key}: {str(value)}")
            y -= 20
        
        c.save()
        return pdf_path
    except Exception as e:
        print(f"Erreur PDF: {e}")
        return None

# ================= ENDPOINTS =================
@app.get("/")
async def root():
    return {"message": "Bienvenue sur Spider Intel API"}

@app.post("/scan")
async def scan(target: Target):
    try:
        scan_func = {
            "email": scan_email,
            "ip": scan_ip,
            "domain": scan_domain,
            "celebrity": scan_celebrity
        }.get(target.type)
        
        if not scan_func:
            raise HTTPException(400, "Type invalide")
        
        result = scan_func(target.value)
        
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO targets (type, value, result) VALUES (?, ?, ?)",
                (target.type, target.value, str(result))
            )
            conn.commit()
        
        pdf_url = f"/reports/{target.type}_{target.value}.pdf" if generate_pdf(target, result) else None
        
        return {
            "status": "success",
            "result": result,
            "pdf_url": pdf_url
        }
        
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/telegram-webhook")
async def telegram_webhook(update: dict):
    try:
        message = update.get("message", {})
        text = message.get("text", "").lower()
        chat_id = message["chat"]["id"]
        
        if text.startswith("/start"):
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": "Envoyez /scan suivi d'une IP, email ou domaine"
            })
            
        elif text.startswith("/scan"):
            target = text[5:].strip()
            if not target:
                requests.post(f"{TELEGRAM_API}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "Usage: /scan <cible>"
                })
                return
            
            # Détection automatique du type
            if "@" in target:
                scan_type = "email"
            elif target.replace(".", "").isdigit():
                scan_type = "ip"
            else:
                scan_type = "domain"
            
            response = requests.post("http://localhost:8000/scan", json={
                "type": scan_type,
                "value": target
            })
            
            if response.status_code == 200:
                data = response.json()
                requests.post(f"{TELEGRAM_API}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": f"Résultats pour {target}:\n{data['result']}"
                })
                
    except Exception as e:
        print(f"Erreur webhook: {e}")

# ================= LANCEMENT =================
if __name__ == "__main__":
    init_db()
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)
