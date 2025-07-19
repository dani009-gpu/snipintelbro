from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, shodan, requests, os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from typing import Optional
import uvicorn

# ================= CONFIGURATION =================
app = FastAPI(title="Spider Intel API", 
             description="API OSINT pour analyses de cybersécurité")

# Autorise toutes les origines pour le développement (à restreindre en production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constantes
DB_NAME = "spiderintel.db"
SHODAN_KEY = "b60fae6f92274daca86121eaf2656737"  # Clé API Shodan

# ================= MODÈLES =================
class Target(BaseModel):
    """Modèle pour les requêtes de scan"""
    type: str  # "email", "ip", "domain"
    value: str
    user_id: Optional[str] = None

# ================= BASE DE DONNÉES =================
def init_db():
    """Initialise la base de données SQLite"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY,
                type TEXT,
                value TEXT UNIQUE,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# ================= SERVICES DE SCAN =================
def scan_email(email: str) -> dict:
    """Analyse un email (simulation avec HaveIBeenPwned-like)"""
    return {
        "status": "success",
        "leaks": ["Adobe (2013)", "LinkedIn (2016)"],
        "is_disposable": False,
        "is_valid": True
    }

def scan_ip(ip: str) -> dict:
    """Analyse une IP avec Shodan"""
    try:
        api = shodan.Shodan(SHODAN_KEY)
        return api.host(ip)
    except Exception:
        # Fallback si Shodan échoue
        return {
            "ip": ip,
            "country": "France",
            "city": "Paris",
            "status": "warning",
            "message": "Shodan non disponible - données simulées"
        }

def scan_domain(domain: str) -> dict:
    """Analyse un domaine (WHOIS/DNS)"""
    return {
        "status": "success",
        "registrar": "Nominal (simulation)",
        "dns": ["ns1.example.com", "ns2.example.com"],
        "creation_date": "2020-01-01"
    }

def generate_pdf(target: Target, result: dict) -> Optional[str]:
    """Génère un rapport PDF des résultats"""
    try:
        os.makedirs('reports', exist_ok=True)
        filename = f"{target.type}_{target.value.replace(' ', '_')}.pdf"
        pdf_path = os.path.join("reports", filename)
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 750, f"Rapport OSINT - {target.type.upper()}")
        
        y = 700
        for key, value in result.items():
            if y < 50:  # Nouvelle page si on arrive en bas
                c.showPage()
                y = 750
            c.drawString(72, y, f"{key}: {str(value)}")
            y -= 20
        
        c.save()
        return f"/reports/{filename}"
    except Exception as e:
        print(f"Erreur PDF: {e}")
        return None

# ================= ENDPOINTS =================
@app.get("/", tags=["Root"])
async def root():
    """Endpoint de bienvenue"""
    return {
        "message": "Bienvenue sur Spider Intel API",
        "endpoints": {
            "/scan": "POST - Lancer un scan (email/ip/domain)",
            "/docs": "Documentation Swagger"
        }
    }

@app.post("/scan", tags=["Scan"])
async def scan(target: Target):
    """
    Endpoint principal pour lancer les scans OSINT
    
    Types supportés:
    - email: Analyse de fuites de données
    - ip: Scan Shodan d'une adresse IP
    - domain: Informations WHOIS/DNS
    """
    try:
        # Correspondance des types avec les fonctions de scan
        scan_func = {
            "email": scan_email,
            "ip": scan_ip,
            "domain": scan_domain
        }.get(target.type.lower())
        
        if not scan_func:
            raise HTTPException(400, "Type invalide. Choisissez entre email, ip ou domain")
        
        # Exécution du scan
        result = scan_func(target.value)
        
        # Sauvegarde en base de données
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO targets (type, value, result) VALUES (?, ?, ?)",
                (target.type, target.value, str(result))
            )
            conn.commit()
        
        # Génération du PDF
        pdf_url = generate_pdf(target, result)
        
        return {
            "status": "success",
            "result": result,
            "pdf_url": pdf_url
        }
        
    except Exception as e:
        raise HTTPException(500, f"Erreur serveur: {str(e)}")

# ================= LANCEMENT =================
if __name__ == "__main__":
    init_db()  # Initialisation de la DB
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Écoute sur toutes les interfaces
        port=8000,       # Port standard pour les APIs
        reload=True       # Recharge automatique en développement
    )
