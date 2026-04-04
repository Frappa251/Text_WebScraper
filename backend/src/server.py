import json
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from urllib.parse import urlparse
from typing import List, Dict

from src.models import ParsedDocument, DomainsResponse, GSEntry, FullGSResponse, EvalInput, EvalResponse, TokenLevelEval
from src.evaluator import calcola_metriche_token
from src.parsers.reddit_parser import parse_reddit_post
from src.parsers.wikipedia_parser import parse_wikipedia_post
from src.parsers.stackoverflow_parser import parse_stackoverflow_post

app = FastAPI(title="Minerva Web Pipeline API - Sapienza")

@app.get("/")
async def root():
    """Reindirizza automaticamente alla documentazione per evitare l'errore 404."""
    return RedirectResponse(url="/docs")


def load_supported_domains() -> List[str]:
    """Legge la lista dei domini da domains.json nella root del progetto."""
    try:
        # Usiamo path relativi come richiesto dalle slide per Docker
        with open("domains.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("domains", [])
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback obbligatorio per evitare crash all'avvio
        return ["www.reddit.com", "stackoverflow.com", "en.wikipedia.org"]


def load_gs_data(domain: str) -> list[dict]:
    """Legge il file GS usando percorsi relativi alla posizione dello script."""
    # 1. Identifica la cartella dove si trova server.py (backend/src/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Risale di due livelli per arrivare alla ROOT del progetto
    # Da backend/src/ -> backend/ -> ROOT/
    root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
    
    # 3. Estrae il nome base (es. 'wikipedia' da 'en.wikipedia.org')
    parts = domain.replace("www.", "").split(".")
    nome_base = parts[1] if len(parts) > 2 else parts[0]
    
    # 4. Costruisce il percorso verso gs_data
    file_path = os.path.join(root_dir, "gs_data", f"{nome_base}_gs.json")
    
    # DEBUG: Stampa il percorso nel terminale così vedi se è giusto
    print(f"DEBUG: Cerco il file GS in: {file_path}")

    if not os.path.exists(file_path):
        print(f"DEBUG: File NON trovato!")
        return []
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("gold_standard", [])
    except Exception as e:
        print(f"ERRORE durante la lettura: {e}")
        return []


# --- ENDPOINTS ---

@app.get("/domains", response_model=DomainsResponse)
async def get_domains():
    """Restituisce la lista dei domini assegnati al gruppo."""
    domini = load_supported_domains()
    return DomainsResponse(domains=domini)


@app.get("/parse", response_model=ParsedDocument)
async def parse_url(url: str = Query(..., description="L'URL da parsare")):
    """Seleziona automaticamente il parser corretto ed esegue il parsing."""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    domini_supportati = load_supported_domains()
    
    if domain not in domini_supportati:
        raise HTTPException(status_code=400, detail="Dominio non supportato")
    
    try:
        # Selezione del parser in base al contenuto del dominio
        if "reddit" in domain:
            risultato = await parse_reddit_post(url)
        elif "wikipedia" in domain:
            risultato = await parse_wikipedia_post(url)
        elif "stackoverflow" in domain:
            risultato = await parse_stackoverflow_post(url)
        else:
            raise HTTPException(status_code=400, detail="Parser non implementato per questo dominio")
            
        # Errore 404: URL irraggiungibile o contenuto vuoto
        if not risultato or not risultato.get("html_text"):
            raise HTTPException(status_code=404, detail="URL irraggiungibile o parsing fallito")
            
        return ParsedDocument(**risultato)
        
    except HTTPException:
        raise
    except Exception as e:
        # Errore 500 per problemi tecnici (es. driver browser mancante)
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@app.get("/gold_standard", response_model=GSEntry)
async def get_gold_standard(url: str = Query(...)):
    """Restituisce l'entry del GS per l'URL dato."""
    domain = urlparse(url).netloc
    if domain not in load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    gs_list = load_gs_data(domain)
    
    for entry in gs_list:
        if entry.get("url") == url:
            return GSEntry(**entry)
            
    raise HTTPException(status_code=404, detail="L'URL non è nel Gold Standard")


@app.get("/full_gold_standard", response_model=FullGSResponse)
async def get_full_gold_standard(domain: str = Query(...)):
    """Restituisce tutto il GS del dominio richiesto."""
    if domain not in load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    gs_list = load_gs_data(domain)
    return FullGSResponse(gold_standard=gs_list)


@app.post("/evaluate", response_model=EvalResponse)
async def evaluate_parsing(data: EvalInput):
    """Calcola metriche tra testo parsato e gold standard."""
    metriche = calcola_metriche_token(data.parsed_text, data.gold_text)
    return EvalResponse(
        token_level_eval=TokenLevelEval(**metriche),
        x_eval={}
    )


@app.get("/full_gs_eval", response_model=EvalResponse)
async def get_full_gs_eval(domain: str = Query(...)):
    """Evaluation aggregata (media) su tutto il GS di un dominio."""
    if domain not in load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    gs_list = load_gs_data(domain)
    if not gs_list:
        raise HTTPException(status_code=404, detail="Nessun dato nel GS per questo dominio")
        
    p, r, f1 = [], [], []
    
    for entry in gs_list:
        try:
            # Parsing live dell'URL del GS
            if "reddit" in domain:
                parsed_data = await parse_reddit_post(entry["url"])
            elif "wikipedia" in domain:
                parsed_data = await parse_wikipedia_post(entry["url"])
            elif "stackoverflow" in domain:
                parsed_data = await parse_stackoverflow_post(entry["url"])
            else:
                continue
                
            # Calcolo metriche sul singolo documento
            m = calcola_metriche_token(parsed_data.get("parsed_text", ""), entry["gold_text"])
            p.append(m["precision"])
            r.append(m["recall"])
            f1.append(m["f1"])
        except Exception:
            # Se un documento fallisce, contribuisce con 0 alla media
            p.append(0.0)
            r.append(0.0)
            f1.append(0.0)
            
    # Calcolo medie
    n = len(gs_list)
    return EvalResponse(
        token_level_eval=TokenLevelEval(
            precision=round(sum(p)/n, 4),
            recall=round(sum(r)/n, 4),
            f1=round(sum(f1)/n, 4)
        ),
        x_eval={}
    )