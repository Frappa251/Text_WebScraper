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
        """
        Legge la lista dei domini supportati dal file domains.json.

        Returns:
            List[str]: Una lista di stringhe contenente i domini supportati. 
                       Restituisce una lista vuota in caso di errore o file non trovato.
        """
        file_path = os.path.join(self.current_dir, "..", "..", "domains.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("domains", [])
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"ATTENZIONE: File non trovato in {os.path.abspath(file_path)}")
            return []

    def load_gs_data(self, domain: str) -> List[Dict[str, Any]]:
        """
        Carica i dati del Gold Standard dal file JSON corrispondente al dominio richiesto.

        Args:
            domain (str): Il nome del dominio (es. 'wikipedia' o 'en.wikipedia.org').

        Returns:
            List[Dict[str, Any]]: Una lista di dizionari, dove ogni dizionario rappresenta 
                                  una entry del Gold Standard. Restituisce una lista vuota se assente.
        """
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
    """
    Reindirizza automaticamente l'utente alla documentazione Swagger (UI) all'avvio dell'API.

    Returns:
        RedirectResponse: Un redirect HTTP verso il percorso '/docs'.
    """
    return RedirectResponse(url="/docs")

@app.get("/domains", response_model=DomainsResponse)
async def get_domains() -> DomainsResponse:
    """
    Restituisce la lista completa dei domini assegnati e supportati dal sistema.

    Returns:
        DomainsResponse: Un oggetto contenente la lista dei domini.
    """
    domini = data_manager.load_supported_domains()
    return DomainsResponse(domains=domini)

@app.get("/parse", response_model=ParsedDocument)
async def parse_url(url: str = Query(..., description="L'URL da parsare")) -> ParsedDocument:
    """
    Riceve un URL, identifica dinamicamente il dominio, avvia il crawler asincrono 
    con il parser appropriato e restituisce il testo estratto in formato Markdown.

    Args:
        url (str): L'URL completo della pagina web da analizzare.

    Returns:
        ParsedDocument: Un oggetto contenente URL, dominio, titolo, HTML originale e Markdown estratto.
    """
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
    """
    Esegue il parsing su un codice HTML fornito direttamente nel body della richiesta, 
    bypassando la fase di crawling.

    Args:
        data (ParseHtmlInput): Oggetto contenente l'URL di riferimento e il codice HTML grezzo.

    Returns:
        ParsedDocument: Un oggetto contenente i dati estratti formattati.
    """
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
    """
    Ricerca e restituisce la singola voce del Gold Standard associata a un URL specifico.

    Args:
        url (str): L'URL esatto da cercare nel Gold Standard.

    Returns:
        GSEntry: L'oggetto contenente il testo Gold Standard e l'HTML storico per quell'URL.
    """
    domain = urlparse(url).netloc
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
        
    for entry in data_manager.load_gs_data(domain):
        if entry.get("url") == url:
            return GSEntry(**entry)
    raise HTTPException(status_code=404, detail="URL non presente nel Gold Standard")

@app.get("/full_gold_standard", response_model=FullGSResponse)
async def get_full_gold_standard(domain: str = Query(...)) -> FullGSResponse:
    """
    Restituisce l'intero blocco di dati del Gold Standard per un dominio specifico.

    Args:
        domain (str): Il dominio di cui si richiede il Gold Standard completo.

    Returns:
        FullGSResponse: L'elenco completo delle entry (URL, HTML, Testo Gold) per quel dominio.
    """
    if domain not in data_manager.load_supported_domains():
        raise HTTPException(status_code=400, detail="Dominio non supportato")
    return FullGSResponse(gold_standard=data_manager.load_gs_data(domain))

@app.post("/evaluate", response_model=EvalResponse)
async def evaluate_parsing(data: EvalInput) -> EvalResponse:
    """
    Calcola le metriche di valutazione (Precision, Recall, F1, Jaccard) confrontando 
    due testi forniti direttamente nella richiesta.

    Args:
        data (EvalInput): Un oggetto contenente il testo estratto dal parser e il testo Gold Standard.

    Returns:
        EvalResponse: I risultati delle metriche calcolate a livello di token.
    """
    result = TextEvaluator.valuta_testo(data.parsed_text, data.gold_text)
    return EvalResponse(
        token_level_eval=TokenLevelEval(**result["token_level_eval"]),
        x_eval=result["x_eval"]
    )

@app.get("/evaluate_url", response_model=EvalResponse)
async def evaluate_url(url: str = Query(...)) -> EvalResponse:
    """
    Esegue il crawling live di un URL, ne estrae il testo e lo valuta immediatamente 
    confrontandolo con il suo corrispondente Gold Standard salvato in locale.

    Args:
        url (str): L'URL della pagina da scansionare e valutare.

    Returns:
        EvalResponse: Le metriche di valutazione risultanti dal confronto.
    """
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
    """
    Esegue una valutazione massiva: recupera l'HTML storico di tutti gli URL nel Gold Standard 
    di un dominio, li passa ai parser e calcola la media globale delle metriche (Precision, Recall, F1).

    Args:
        domain (str): Il dominio su cui eseguire la valutazione aggregata.

    Returns:
        EvalResponse: Le metriche di valutazione medie per l'intero dominio.
    """
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