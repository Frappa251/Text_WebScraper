import json
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from urllib.parse import urlparse
from typing import List, Dict, Any

from .models import (
    ParsedDocument,
    ParseHtmlInput,
    DomainsResponse,
    GSEntry,
    FullGSResponse,
    EvalInput,
    EvalResponse,
    TokenLevelEval
)
from .evaluator import TextEvaluator
from .parsers.wikipedia_parser import WikipediaParser
from .parsers.rockol_parser import RockolParser
from .parsers.grammy_parser import GrammyParser
from .parsers.accuweather_parser import AccuweatherParser

class DataManager:
    """Classe responsabile del caricamento dei dati statici (Domini e Gold Standard)."""
    
    def __init__(self) -> None:
        self.current_dir = os.path.dirname(__file__)

    def load_supported_domains(self) -> List[str]:
        """Legge la lista dei domini da domains.json usando un path relativo robusto."""
        file_path = os.path.join(self.current_dir, "..", "..", "domains.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("domains", [])
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"ATTENZIONE: File non trovato in {os.path.abspath(file_path)}")
            return []

    def load_gs_data(self, domain: str) -> List[Dict[str, Any]]:
        """Legge il file JSON del Gold Standard corrispondente al dominio richiesto."""
        parts = domain.replace("www.", "").split(".")
        nome_base = parts[1] if len(parts) > 2 else parts[0]
        file_path = os.path.join(self.current_dir, "..", "..", "gs_data", f"{nome_base}_gs.json")
        
        if not os.path.exists(file_path):
            return []
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("gold_standard", [])
        except Exception:
            return []

app = FastAPI(title="Minerva Web Pipeline API - Sapienza")
data_manager = DataManager()

@app.get("/")
async def root() -> RedirectResponse:
    """Reindirizza automaticamente alla documentazione Swagger."""
    return RedirectResponse(url="/docs")

@app.get("/domains", response_model=DomainsResponse)
async def get_domains() -> DomainsResponse:
    """Restituisce la lista dei domini assegnati al gruppo."""
    domini = data_manager.load_supported_domains()
    return DomainsResponse(domains=domini)

@app.get("/parse", response_model=ParsedDocument)
async def parse_url(url: str = Query(..., description="L'URL da parsare")) -> ParsedDocument:
    """Seleziona dinamicamente il parser corretto ed estrae il contenuto dall'URL."""
    domain = urlparse(url).netloc
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
    
    try:
        if "wikipedia" in domain:
            risultato = await WikipediaParser().parse(url)
        elif "rockol" in domain:
            risultato = await RockolParser().parse(url)
        elif "grammy" in domain:
            risultato = await GrammyParser().parse(url)
        elif "accuweather" in domain:
            risultato = await AccuweatherParser().parse(url)
        else:
            raise HTTPException(status_code=400, detail="Parser non implementato")
            
        if not risultato or not risultato.get("html_text"):
            raise HTTPException(status_code=404, detail="Parsing fallito")
            
        return ParsedDocument(**risultato)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")

@app.post("/parse", response_model=ParsedDocument)
async def parse_html(data: ParseHtmlInput) -> ParsedDocument:
    """Seleziona dinamicamente il parser corretto ed esegue il parsing su html_text diretto."""
    domain = urlparse(data.url).netloc
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")

    try:
        if "wikipedia" in domain:
            risultato = await WikipediaParser().parse_html(data.url, data.html_text)
        elif "rockol" in domain:
            risultato = await RockolParser().parse_html(data.url, data.html_text)
        elif "grammy" in domain:
            risultato = await GrammyParser().parse_html(data.url, data.html_text)
        elif "accuweather" in domain:
            risultato = await AccuweatherParser().parse_html(data.url, data.html_text)
        else:
            raise HTTPException(status_code=400, detail="Parser non implementato")

        if not risultato or not risultato.get("html_text"):
            raise HTTPException(status_code=404, detail="Parsing fallito")

        return ParsedDocument(**risultato)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")

@app.get("/gold_standard", response_model=GSEntry)
async def get_gold_standard(url: str = Query(...)) -> GSEntry:
    """Restituisce la singola entry del Gold Standard associata all'URL."""
    domain = urlparse(url).netloc
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    for entry in data_manager.load_gs_data(domain):
        if entry.get("url") == url:
            return GSEntry(**entry)
    raise HTTPException(status_code=404, detail="URL non presente nel Gold Standard")

@app.get("/full_gold_standard", response_model=FullGSResponse)
async def get_full_gold_standard(domain: str = Query(...)) -> FullGSResponse:
    """Restituisce l'intero Gold Standard per il dominio indicato."""
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
    return FullGSResponse(gold_standard=data_manager.load_gs_data(domain))

@app.post("/evaluate", response_model=EvalResponse)
async def evaluate_parsing(data: EvalInput) -> EvalResponse:
    """Calcola le metriche di valutazione tra il testo estratto e il Gold Standard."""
    result = TextEvaluator.valuta_testo(data.parsed_text, data.gold_text)
    return EvalResponse(
        token_level_eval=TokenLevelEval(**result["token_level_eval"]),
        x_eval=result["x_eval"]
    )

@app.get("/evaluate_url", response_model=EvalResponse)
async def evaluate_url(url: str = Query(...)) -> EvalResponse:
    """Esegue il parsing di un URL e lo valuta contro il suo Gold Standard."""
    domain = urlparse(url).netloc
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
    
    gs_list = data_manager.load_gs_data(domain)
    gold_entry = next((e for e in gs_list if e.get("url") == url), None)
    if not gold_entry:
        raise HTTPException(status_code=404, detail="URL non nel Gold Standard")
    
    try:
        if "wikipedia" in domain:
            parsed_data = await WikipediaParser().parse(url)
        elif "rockol" in domain:
            parsed_data = await RockolParser().parse(url)
        elif "grammy" in domain:
            parsed_data = await GrammyParser().parse(url)
        elif "accuweather" in domain:
            parsed_data = await AccuweatherParser().parse(url)
        else:
            raise HTTPException(status_code=400, detail="Parser non implementato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    if not parsed_data.get("parsed_text"):
        raise HTTPException(status_code=404, detail="Parsing vuoto")
    
    result = TextEvaluator.valuta_testo(parsed_data["parsed_text"], gold_entry["gold_text"])
    return EvalResponse(
        token_level_eval=TokenLevelEval(**result["token_level_eval"]),
        x_eval=result["x_eval"]
    )

@app.get("/full_gs_eval", response_model=EvalResponse)
async def get_full_gs_eval(domain: str = Query(...)) -> EvalResponse:
    """Esegue il parsing e la valutazione mediata su tutto il GS di un dominio."""
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    gs_list = data_manager.load_gs_data(domain)
    if not gs_list:
        raise HTTPException(status_code=404, detail="Nessun GS trovato")
        
    p, r, f1, jaccard_list = [], [], [], []
    
    for entry in gs_list:
        try:
            if "wikipedia" in domain:
                parsed_data = await WikipediaParser().parse_html(entry["url"], entry["html_text"])
            elif "rockol" in domain:
                parsed_data = await RockolParser().parse_html(entry["url"], entry["html_text"])
            elif "grammy" in domain:
                parsed_data = await GrammyParser().parse_html(entry["url"], entry["html_text"])
            elif "accuweather" in domain:
                parsed_data = await AccuweatherParser().parse_html(entry["url"], entry["html_text"])
            else:
                continue
                
            result = TextEvaluator.valuta_testo(parsed_data.get("parsed_text", ""), entry["gold_text"])
            m = result["token_level_eval"]
            p.append(m["precision"])
            r.append(m["recall"])
            f1.append(m["f1"])
            jaccard_list.append(result["x_eval"]["jaccard_similarity"])
        except Exception:
            p.append(0.0)
            r.append(0.0)
            f1.append(0.0)
            jaccard_list.append(0.0)
            
    n = len(gs_list)
    return EvalResponse(
        token_level_eval=TokenLevelEval(
            precision=round(sum(p) / n, 4),
            recall=round(sum(r) / n, 4),
            f1=round(sum(f1) / n, 4)
        ),
        x_eval={"jaccard_similarity": round(sum(jaccard_list) / n, 4)}
    )