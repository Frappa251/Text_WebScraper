import asyncio
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def parse_accuweather_post(url: str) -> Dict[str, Any]:
    """
    Estrae le previsioni meteo da AccuWeather.
    Rimuove pubblicità, barre laterali, menu di navigazione e banner.
    """
    dominio = urlparse(url).netloc
    dati: Dict[str, Any] = {
        "url": url, 
        "domain": dominio, 
        "title": "", 
        "html_text": "", 
        "parsed_text": ""
    }

    # Header essenziali: AccuWeather blocca spesso i bot se non c'è un User-Agent valido
    headers_custom = {
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    browser_cfg = BrowserConfig(
        headless=True,
        headers=headers_custom
    )
    
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success:
            return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        # 1. Estrazione del Titolo (Location e tipo di previsione)
        tag_titolo = soup.find("h1") or soup.find("title")
        titolo_testo = tag_titolo.get_text(strip=True) if tag_titolo else "AccuWeather Forecast"
        
        # Pulizia del titolo (es: "Rome, Lazio Weather Forecast | AccuWeather" -> "Rome, Lazio Weather Forecast")
        if "|" in titolo_testo:
            titolo_testo = titolo_testo.split("|")[0].strip()
            
        dati["title"] = titolo_testo

        # 2. Selezione dell'area principale (Accuweather usa "page-column-1" per i dati meteo principali)
        main_content = soup.find("div", class_="page-column-1") or \
                       soup.find("div", class_="two-column-page-content") or \
                       soup.find("main")

        # 3 & 4. Pulizia ed Elaborazione
        if main_content:
            # Lista di selettori per eliminare il "rumore" specifico di AccuWeather
            selectors_da_eliminare = [
                "nav", "footer", "header", "script", "style", "noscript",
                ".page-column-2",      # Barra laterale (spesso contiene news e ad)
                ".ad",                 # Elementi pubblicitari
                ".ad-container",       # Contenitori di banner
                "[id^='ad-']",         # ID che iniziano per "ad-"
                ".breadcrumbs",        # Navigazione a briciole di pane
                ".policy-banner",      # Banner dei cookie
                ".banner-button",
                "svg"                  # Rimuove le icone SVG che sporcano il markdown
            ]
            
            for noisy in main_content.select(", ".join(selectors_da_eliminare)):
                noisy.decompose()

            # Convertiamo in markdown
            testo_markdown = md(str(main_content), heading_style="ATX")

            # Pulizia delle righe vuote mantenendo la formattazione
            parsed_lines = []
            for line in testo_markdown.splitlines():
                # Rimuoviamo gli spazi per capire se la riga è vuota, ma aggiungiamo la riga originale
                if line.strip():
                    parsed_lines.append(line)

            # Uniamo con a capo singoli
            corpo_pulito = "\n".join(parsed_lines).strip()
            
            # Formattiamo il risultato finale con l'H1 per il titolo
            if titolo_testo:
                dati["parsed_text"] = f"# {titolo_testo}\n\n{corpo_pulito}"
            else:
                dati["parsed_text"] = corpo_pulito
                
        else:
            # Fallback
            testo_fallback = result.markdown
            dati["parsed_text"] = f"# {titolo_testo}\n\n{testo_fallback}" if titolo_testo else testo_fallback

        return dati

if __name__ == "__main__":
    # Test locale
    url_di_prova = "https://www.accuweather.com/en/it/rome/213490/weather-forecast/213490"
    risultato_test = asyncio.run(parse_accuweather_post(url_di_prova))
    
    print(f"TITOLO: {risultato_test['title']}")
    print("-" * 50)
    print(risultato_test['parsed_text'][:1000]) # Stampa solo i primi 1000 caratteri