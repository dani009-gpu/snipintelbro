"""SPIDER INTEL - BACKEND COMPLET"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import uvicorn
from typing import Optional
import datetime

app = FastAPI()

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration de base
DB_NAME = "spiderintel.db"

# Modèles
class Target(BaseModel):
    type: str  # "email", "ip", "domain", "username"
    value: str

# Initialisation DB
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY,
                type TEXT,
                value TEXT UNIQUE,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# Fonctions de scan
def scan_email(email: str):
    return {
        "status": "success",
        "email": email,
        "is_disposable": False,
        "leaks": ["Adobe", "LinkedIn"]
    }

def scan_ip(ip: str):
    return {
        "status": "success",
        "ip": ip,
        "location": "Simulation: Paris, France",
        "isp": "Simulation ISP"
    }

def scan_domain(domain: str):
    return {
        "status": "success",
        "domain": domain,
        "registrar": "Simulation Registrar",
        "creation_date": "2020-01-01"
    }

def scan_username(username: str):
    return {
        "status": "success",
        "username": username,
        "social_media": {
            "twitter": f"https://twitter.com/{username}",
            "github": f"https://github.com/{username}"
        }
    }

# Génération PDF
def generate_pdf(target: Target, result: dict):
    try:
        if not os.path.exists('reports'):
            os.makedirs('reports')
        
        filename = f"{target.type}_{target.value.replace(' ', '_')[:50]}.pdf"
        pdf_path = os.path.join("reports", filename)
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        
        # En-tête
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 750, f"Rapport OSINT - {target.type.upper()}")
        c.drawString(72, 730, f"Cible: {target.value}")
        
        # Contenu
        y = 700
        c.setFont("Helvetica", 12)
        for key, value in result.items():
            if y < 50:
                c.showPage()
                y = 750
            c.drawString(72, y, f"{key}: {str(value)}")
            y -= 20
        
        c.save()
        return pdf_path
    except Exception as e:
        print(f"Erreur génération PDF: {e}")
        return None

# Routes
@app.post("/scan")
async def scan(target: Target):
    try:
        # Sélection de la fonction de scan
        scan_functions = {
            "email": scan_email,
            "ip": scan_ip,
            "domain": scan_domain,
            "username": scan_username
        }
        
        if target.type not in scan_functions:
            raise HTTPException(400, "Type de cible non supporté")
        
        result = scan_functions[target.type](target.value)
        
        # Sauvegarde en DB
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO targets (type, value, result) VALUES (?, ?, ?)",
                (target.type, target.value, str(result))
            )
            conn.commit()
        
        # Génération PDF
        pdf_path = generate_pdf(target, result)
        if not pdf_path:
            raise HTTPException(500, "Erreur génération PDF")
        
        return {
            "status": "success",
            "target": target,
            "result": result,
            "pdf_url": f"/{pdf_path}"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Erreur serveur: {str(e)}")

# Point d'entrée
if __name__ == "__main__":
    init_db()
    uvicorn.run(
        "backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug"
    )
