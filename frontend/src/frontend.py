import requests
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

app = FastAPI(title="Minerva Web UI")

# Specifica la cartella dove Jinja2 andrà a pescare i file HTML
templates = Jinja2Templates(directory="templates")

# Indirizzo del tuo backend (il server di logica)
BACKEND_URL = "http://127.0.0.1:8003"

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """
    Carica la homepage. Prima interroga il backend per farsi dare 
    tutti gli URL del Gold Standard per popolare la tendina.
    """
    gs_urls = []
    try:
        # 1. Chiede i domini supportati
        dom_res = requests.get(f"{BACKEND_URL}/domains")
        if dom_res.status_code == 200:
            domini = dom_res.json().get("domains", [])
            # 2. Per ogni dominio, chiede tutti gli URL del GS
            for d in domini:
                gs_res = requests.get(f"{BACKEND_URL}/full_gold_standard?domain={d}")
                if gs_res.status_code == 200:
                    entries = gs_res.json().get("gold_standard", [])
                    for entry in entries:
                        gs_urls.append(entry.get("url"))
    except Exception as e:
        print(f"Errore di connessione al backend: {e}")

    # Passa la lista di URL all'HTML tramite Jinja2
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"gs_urls": gs_urls}
    )


@app.post("/process", response_class=HTMLResponse)
def process_url(request: Request, url_libero: str = Form(""), url_tendina: str = Form("")):
    """
    Riceve l'URL inserito o selezionato, interroga il backend 
    e restituisce la pagina dei risultati.
    """
    # Dà priorità alla tendina, se vuota usa il campo di testo libero
    target_url = url_tendina if url_tendina else url_libero
    
    if not target_url:
        return templates.TemplateResponse(
            request=request, 
            name="result.html", 
            context={"error": "Nessun URL fornito."}
        )

    try:
        # 1. Chiede al backend di fare il parsing
        parse_res = requests.get(f"{BACKEND_URL}/parse", params={"url": target_url})
        if parse_res.status_code != 200:
            return templates.TemplateResponse(
                request=request, 
                name="result.html", 
                context={"error": f"Errore dal parser: {parse_res.text}"}
            )
        
        parsed_data = parse_res.json()
        html_text = parsed_data.get("html_text", "")
        parsed_text = parsed_data.get("parsed_text", "")

        has_gs = False
        gold_text = ""
        metrics = None

        # 2. Controlla se l'URL ha un Gold Standard associato
        gs_res = requests.get(f"{BACKEND_URL}/gold_standard", params={"url": target_url})
        if gs_res.status_code == 200:
            has_gs = True
            gold_text = gs_res.json().get("gold_text", "")

            # 3. Se c'è il GS, chiede al backend di calcolare le metriche
            eval_payload = {"parsed_text": parsed_text, "gold_text": gold_text}
            eval_res = requests.post(f"{BACKEND_URL}/evaluate", json=eval_payload)
            if eval_res.status_code == 200:
                metrics = eval_res.json().get("token_level_eval", {})

        # Passa tutti i dati ottenuti al template dei risultati
        return templates.TemplateResponse(
            request=request, 
            name="result.html", 
            context={
                "url": target_url,
                "html_text": html_text,
                "parsed_text": parsed_text,
                "has_gs": has_gs,
                "gold_text": gold_text,
                "metrics": metrics
            }
        )

    except requests.exceptions.ConnectionError:
        return templates.TemplateResponse(
            request=request, 
            name="result.html", 
            context={"error": "Il server di logica (backend) non risponde. Assicurati che sia acceso sulla porta 8003."}
        )