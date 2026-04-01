import json
import os
from fastapi import FastAPI, HTTPException, Query
from urllib.parse import urlparse

# Importiamo i modelli e l'evaluator
from src.models import (ParsedDocument, DomainsResponse, GSEntry, 
                        FullGSResponse, EvalInput, EvalResponse, TokenLevelEval)
from src.evaluator import calcola_metriche_token

# Importiamo i parser (Assicurati che i nomi corrispondano ai vostri)
from src.parsers.reddit_parser import parse_reddit_post
# from src.parsers.wikipedia_parser import parse_wikipedia_post # Scommenta quando pronto

app = FastAPI(title="Web Scraper & Evaluator API")


def load_supported_domains() -> list[str]:
    """Legge la lista dei domini da domains.json nella root del progetto."""
    try:
        with open("domains.json", "r") as f:
            data = json.load(f)
            return data.get("domains", [])
    except FileNotFoundError:
        return ["www.reddit.com", "it.wikipedia.org"] # Fallback per sicurezza

def load_gs_data(domain: str) -> list[dict]:
    """Legge il file Gold Standard specifico per il dominio dalla cartella gs_data/"""
    # Trasforma 'www.reddit.com' in 'reddit_gs.json'
    nome_base = domain.replace("www.", "").split(".")[0]
    file_path = f"gs_data/{nome_base}_gs.json"
    
    if not os.path.exists(file_path):
        return []
        
    with open(file_path, "r") as f:
        return json.load(f).get("gold_standard", [])


@app.get("/domains", response_model=DomainsResponse)
async def get_domains():
    domini = load_supported_domains()
    return DomainsResponse(domains=domini)


@app.get("/parse", response_model=ParsedDocument)
async def parse_url(url: str = Query(..., description="L'URL da parsare")):
    domain = urlparse(url).netloc
    domini_supportati = load_supported_domains()
    
    if domain not in domini_supportati:
        raise HTTPException(status_code=400, detail="Dominio non supportato")
    
    # Selezione dinamica del parser
    try:
        if "reddit" in domain:
            risultato = await parse_reddit_post(url)
        elif "wikipedia" in domain:
            # risultato = await parse_wikipedia_post(url)
            pass
        else:
            raise HTTPException(status_code=400, detail="Parser non implementato per questo dominio")
            
        # Gestione Errore: URL irraggiungibile (se il parser restituisce campi vuoti)
        if not risultato.get("html_text"):
            raise HTTPException(status_code=404, detail="URL irraggiungibile o parsing fallito")
            
        return ParsedDocument(**risultato)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno del parser: {str(e)}")


@app.get("/gold_standard", response_model=GSEntry)
async def get_gold_standard(url: str = Query(...)):
    domain = urlparse(url).netloc
    if domain not in load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    gs_list = load_gs_data(domain)
    
    # Cerca l'URL specifico nel Gold Standard
    for entry in gs_list:
        if entry.get("url") == url:
            return GSEntry(**entry)
            
    raise HTTPException(status_code=404, detail="L'URL non è presente nel Gold Standard")


@app.get("/full_gold_standard", response_model=FullGSResponse)
async def get_full_gold_standard(domain: str = Query(...)):
    if domain not in load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    gs_list = load_gs_data(domain)
    return FullGSResponse(gold_standard=gs_list)


@app.post("/evaluate", response_model=EvalResponse)
async def evaluate_parsing(data: EvalInput):
    metriche = calcola_metriche_token(data.parsed_text, data.gold_text)
    return EvalResponse(
        token_level_eval=TokenLevelEval(**metriche),
        x_eval={} # Spazio per eventuali metriche extra future
    )


@app.get("/full_gs_eval", response_model=EvalResponse)
async def get_full_gs_eval(domain: str = Query(...)):
    if domain not in load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    gs_list = load_gs_data(domain)
    if not gs_list:
        raise HTTPException(status_code=404, detail="Gold Standard vuoto per questo dominio")
        
    precisions, recalls, f1s = [], [], []
    
    # Esegue il parsing e la valutazione per ogni elemento del GS
    for entry in gs_list:
        url = entry["url"]
        gold_text = entry["gold_text"]
        
        try:
            # Richiama il parser corretto
            if "reddit" in domain:
                parsed_data = await parse_reddit_post(url)
            elif "wikipedia" in domain:
                # parsed_data = await parse_wikipedia_post(url)
                pass
                
            parsed_text = parsed_data.get("parsed_text", "")
            
            # Calcola e accumula le metriche
            metriche = calcola_metriche_token(parsed_text, gold_text)
            precisions.append(metriche["precision"])
            recalls.append(metriche["recall"])
            f1s.append(metriche["f1"])
            
        except Exception:
            # Se un URL fallisce, conta come 0
            precisions.append(0.0)
            recalls.append(0.0)
            f1s.append(0.0)
            
    # Aggregazione tramite media
    tot_elementi = len(gs_list)
    avg_precision = sum(precisions) / tot_elementi
    avg_recall = sum(recalls) / tot_elementi
    avg_f1 = sum(f1s) / tot_elementi
    
    return EvalResponse(
        token_level_eval=TokenLevelEval(
            precision=round(avg_precision, 4),
            recall=round(avg_recall, 4),
            f1=round(avg_f1, 4)
        ),
        x_eval={}
    )