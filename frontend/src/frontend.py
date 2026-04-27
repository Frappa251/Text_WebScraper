import os
import requests
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

class BackendClient:
    """Classe client per gestire in modo object-oriented la comunicazione col Backend."""
    
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def get_supported_gs_urls(self) -> List[str]:
        """
        Recupera la lista di tutti gli URL presenti nei Gold Standard.

        Returns: 
            List[str]: restituisce una lista di stringhe degli Url del gold standard
        """
        gs_urls: List[str] = []
        try:
            dom_res = requests.get(f"{self.base_url}/domains")
            if dom_res.status_code == 200:
                domini = dom_res.json().get("domains", [])
                for d in domini:
                    gs_res = requests.get(f"{self.base_url}/full_gold_standard?domain={d}")
                    if gs_res.status_code == 200:
                        entries = gs_res.json().get("gold_standard", [])
                        gs_urls.extend([entry.get("url") for entry in entries])
        except requests.RequestException:
            pass
        return gs_urls

    def parse_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Richiede al backend il parsing di un URL specificato.

        Args: 
            url (str): URL di uno specifico sito

        Returns:
            Optional[Dict[str, Any]]: restituisce il parsing dell'url richiesto
        """
        res = requests.get(f"{self.base_url}/parse", params={"url": url})
        if res.status_code == 200:
            return res.json()
        return None

    def get_gold_standard(self, url: str) -> str:
        """
    Controlla se esiste il GS per l'URL e restituisce il testo gold.

    Args:
        url (str): URL di cui recuperare il Gold Standard

    Returns:
        str: restituisce il testo del Gold Standard se presente, altrimenti una stringa vuota
    """
        res = requests.get(f"{self.base_url}/gold_standard", params={"url": url})
        if res.status_code == 200:
            return res.json().get("gold_text", "")
        return ""

    def evaluate(self, parsed_text: str, gold_text: str) -> Optional[Dict[str, Any]]:
        """
    Invia i testi al backend per il calcolo di TUTTE le metriche.

    Args:
        parsed_text (str): testo pulito estratto dal parser
        gold_text (str): testo di riferimento del Gold Standard

    Returns:
        Optional[Dict[str, Any]]: restituisce un dizionario contenente le metriche calcolate o None in caso di errore
    """
        payload = {"parsed_text": parsed_text, "gold_text": gold_text}
        res = requests.post(f"{self.base_url}/evaluate", json=payload)
        if res.status_code == 200:
            return res.json()  
        return None

app = FastAPI(title="Minerva Web UI")

# Calcola il percorso assoluto della cartella templates partendo da questo file (frontend/src)
current_dir = os.path.dirname(__file__)
templates_dir = os.path.join(current_dir, "..", "templates")

# Inizializza Jinja2 con il percorso calcolato in modo sicuro
templates = Jinja2Templates(directory=templates_dir)

# Inizializziamo la classe client
api_client = BackendClient(base_url=os.getenv("BACKEND_URL", "http://127.0.0.1:8003"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """
    Endpoint che carica la homepage, popolando la tendina con gli URL noti.

    Args:
        request (Request): l'oggetto della richiesta HTTP di FastAPI

    Returns:
        HTMLResponse: restituisce la pagina HTML della homepage renderizzata
    """
    gs_urls = api_client.get_supported_gs_urls()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"gs_urls": gs_urls}
    )

@app.post("/process", response_class=HTMLResponse)
def process_url(request: Request, url_libero: str = Form(""), url_tendina: str = Form("")) -> HTMLResponse:
    """
    Endpoint che elabora la richiesta form, interroga il backend e renderizza i risultati.

    Args:
        request (Request): l'oggetto della richiesta HTTP di FastAPI
        url_libero (str): URL inserito manualmente dall'utente nel campo di testo
        url_tendina (str): URL selezionato dall'utente dal menu a tendina

    Returns:
        HTMLResponse: restituisce la pagina HTML con i risultati dell'estrazione e della valutazione
    """
    target_url = url_tendina if url_tendina else url_libero
    
    if not target_url:
        return templates.TemplateResponse(request=request, name="result.html", context={"error": "Nessun URL fornito."})

    try:
        parsed_data = api_client.parse_url(target_url)
        if not parsed_data:
            return templates.TemplateResponse(request=request, name="result.html", context={"error": "Errore dal parser."})
        
        gold_text = api_client.get_gold_standard(target_url)
        has_gs = bool(gold_text)
        
        metrics = None
        x_eval = None

        if has_gs:
            eval_result = api_client.evaluate(parsed_data.get("parsed_text", ""), gold_text)
            if eval_result:
                metrics = eval_result.get("token_level_eval", {})
                x_eval = eval_result.get("x_eval", {})

        return templates.TemplateResponse(
            request=request, 
            name="result.html", 
            context={
                "url": target_url,
                "html_text": parsed_data.get("html_text", ""),
                "parsed_text": parsed_data.get("parsed_text", ""),
                "has_gs": has_gs,
                "gold_text": gold_text,
                "metrics": metrics,
                "x_eval": x_eval  
            }
        )

    except requests.exceptions.ConnectionError:
        return templates.TemplateResponse(
            request=request, 
            name="result.html", 
            context={"error": "Il backend non risponde. Assicurati che sia attivo."}
        )