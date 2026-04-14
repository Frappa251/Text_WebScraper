import asyncio
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def parse_rockol_post(url: str) -> Dict[str, Any]:
    """
    Estrae il titolo e il contenuto degli articoli di Rockol.it.
    Rimuove immagini, widget social, pubblicità e box correlati.
    """
    dominio = urlparse(url).netloc
    dati: Dict[str, Any] = {
        "url": url, 
        "domain": dominio, 
        "title": "", 
        "html_text": "", 
        "parsed_text": ""
    }

    # Configurazione Browser (forziamo l'italiano visto il dominio)
    headers_it = {
        "Accept-Language": "it-IT,it;q=0.9",
    }
    browser_cfg = BrowserConfig(headless=True, headers=headers_it)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success:
            return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        # 1. Estrazione del Titolo (Rockol usa h1 per le news)
        tag_titolo = soup.find("h1")
        dati["title"] = tag_titolo.get_text(strip=True) if tag_titolo else "Titolo non trovato"

        # 2. Identificazione del contenuto principale
        # Solitamente Rockol racchiude l'articolo in tag <article> o div specifici
        main_content = soup.find("article") or soup.find("div", class_="article-text")
        
        if main_content:
            # 1. BARRIERA HTML: Pulizia più aggressiva
            selectors_da_eliminare = [
                "img", "figure", "picture",      
                ".related-box", ".correlati",     
                ".social-share", ".social-buttons",
                "script", "style", "iframe",      
                ".adv", ".advertising", ".banner",
                ".tags-container", ".author-box",
                # NUOVI SELETTORI PER ROCKOL:
                ".artist-menu", ".artist-nav", # Rimuove il menu Biografia/Articoli
                ".breadcrumbs", "aside", ".sidebar", ".widget", # Rimuove colonne laterali
                ".video-ros" # Rimuove il player video nascosto
            ]
            
            for selector in selectors_da_eliminare:
                for element in main_content.select(selector):
                    element.decompose()

            # Trasformazione in Markdown
            testo_markdown = md(str(main_content), heading_style="ATX")
            
            parsed_lines = []
            if dati["title"]:
                parsed_lines.append(f"# {dati['title']}")
                
            # 2. BARRIERA MARKDOWN: Filtraggio intelligente riga per riga
            for line in testo_markdown.splitlines():
                clean_line = line.strip()
                
                # TRUCCO INFALLIBILE: Se inizia la sezione "Ultimissime", fermiamo la lettura dell'articolo!
                if "Ultimissime" in clean_line and clean_line.startswith("#"):
                    break
                    
                # Ignoriamo i residui del menu di navigazione superiore dell'artista
                if "Torna all'homepage" in clean_line or "[Biografia]" in clean_line or "[Articoli]" in clean_line:
                    continue
                    
                # Ignoriamo eventuali link orfani di immagini sfuggite alla pulizia HTML
                if clean_line.startswith("](") and ".png" in clean_line:
                    continue

                # Teniamo solo righe che hanno sostanza testuale
                if clean_line and any(c.isalpha() for c in clean_line):
                    if len(clean_line) > 10:
                        parsed_lines.append(clean_line)

            dati["parsed_text"] = "\n\n".join(parsed_lines).strip()

        return dati