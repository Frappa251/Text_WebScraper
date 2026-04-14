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
            # 3. Pulizia Aggressiva (Cosa togliere per la Precision)
            selectors_da_eliminare = [
                "img", "figure", "picture",      # Rimuoviamo le immagini (richiesta prof)
                ".related-box", ".correlati",     # Articoli correlati
                ".social-share", ".social-buttons",# Bottoni social
                "script", "style", "iframe",      # Codice tecnico
                ".adv", ".advertising", ".banner",# Pubblicità
                ".tags-container", ".author-box"  # Tag e info autore (spesso non nel GS)
            ]
            
            for selector in selectors_da_eliminare:
                for element in main_content.select(selector):
                    element.decompose()

            # 4. Trasformazione in Markdown
            testo_markdown = md(str(main_content), heading_style="ATX")
            
            # 5. Pulizia righe superflue
            parsed_lines = []
            if dati["title"]:
                parsed_lines.append(f"# {dati['title']}")
                
            for line in testo_markdown.splitlines():
                clean_line = line.strip()
                # Teniamo solo righe che hanno sostanza testuale
                if clean_line and any(c.isalpha() for c in clean_line):
                    # Evitiamo di tenere link brevi di navigazione
                    if len(clean_line) > 10:
                        parsed_lines.append(clean_line)

            dati["parsed_text"] = "\n\n".join(parsed_lines).strip()
        else:
            # Fallback se non trova il tag <article>
            dati["parsed_text"] = result.markdown

        return dati