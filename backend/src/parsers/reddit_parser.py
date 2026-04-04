import asyncio
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def parse_reddit_post(url: str) -> Dict[str, Any]:
    dominio = urlparse(url).netloc
    dati: Dict[str, Any] = {
        "url": url, 
        "domain": dominio, 
        "title": "", 
        "html_text": "", 
        "parsed_text": ""
    }

    headers_inglesi = {
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    browser_cfg = BrowserConfig(
        headless=True,
        headers=headers_inglesi
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

        # 1. Estrazione del Titolo
        tag_titolo = soup.find("h1") or soup.find("title")
        titolo_testo = tag_titolo.get_text(strip=True) if tag_titolo else ""
        
        # Pulizia del titolo (rimuove il suffisso standard di Reddit)
        if " : " in titolo_testo:
            titolo_testo = titolo_testo.split(" : ")[0].strip()
            
        dati["title"] = titolo_testo

        # 2. Selezione del corpo del post
        main_content = soup.find("div", {"slot": "text-body"}) or \
                       soup.find("div", {"data-test-id": "post-content"}) or \
                       soup.find("shreddit-post")

        # 3 & 4. Elaborazione e unione del contenuto
        if main_content:
            # Rimuoviamo gli elementi di UI "rumorosi" per non sporcare il markdown
            selectors_da_eliminare = [
                "button", "faceplate-hovercard", "shreddit-post-flair", 
                ".reward-button", "i", "svg", "aside"
            ]
            for noisy in main_content.select(", ".join(selectors_da_eliminare)):
                noisy.decompose()

            # Convertiamo in markdown preservando la formattazione nativa (grassetti, liste, etc.)
            testo_markdown = md(str(main_content), heading_style="ATX")

            # Set di parole chiave da ignorare se appaiono DA SOLE su una riga
            blacklist_keywords = {"share", "reply", "save", "comment", "award", "report", "vote"}
            parsed_lines = []
            
            for line in testo_markdown.splitlines():
                # Ignoriamo la riga solo se contiene ESATTAMENTE una parola in blacklist (scartando gli spazi)
                if line.strip().lower() in blacklist_keywords:
                    continue
                
                # Aggiungiamo la riga intatta, preservando l'indentazione e i marcatori Markdown
                parsed_lines.append(line)

            # Ricostruiamo il corpo del post unendo le righe. 
            # Il \n singolo è sufficiente perché markdownify ha già spaziato i paragrafi.
            corpo_pulito = "\n".join(parsed_lines).strip()
            
            # Uniamo il titolo (formattato come H1 Markdown) e il corpo pulito
            if titolo_testo:
                dati["parsed_text"] = f"# {titolo_testo}\n\n{corpo_pulito}"
            else:
                dati["parsed_text"] = corpo_pulito
                
        else:
            # Fallback: se non trova il div principale, usiamo il markdown generato automaticamente da crawl4ai
            testo_fallback = result.markdown
            dati["parsed_text"] = f"# {titolo_testo}\n\n{testo_fallback}" if titolo_testo else testo_fallback

        return dati