import asyncio
import re
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

    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success:
            return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        # 1. Titolo pulito
        tag_titolo = soup.find("h1")
        dati["title"] = tag_titolo.get_text(strip=True) if tag_titolo else ""

        # 2. Selezione mirata del corpo del post
        # Cerchiamo specificamente il div che contiene il TESTO del post, non tutto lo shreddit-post
        main_content = soup.find("div", {"slot": "text-body"}) or \
                       soup.find("div", {"data-test-id": "post-content"}) or \
                       soup.find("shreddit-post")

        if main_content:
            # Pulizia aggressiva degli elementi UI che sporcano la Precision
            selectors_da_eliminare = [
                "button", "faceplate-hovercard", "shreddit-post-flair", 
                ".reward-button", "i", "svg", "aside"
            ]
            for noisy in main_content.select(", ".join(selectors_da_eliminare)):
                noisy.decompose()

            # 3. Conversione in Markdown
            testo_markdown = md(str(main_content), heading_style="ATX")

            # 4. Filtro per righe di "navigazione" o "social"
            # Escludiamo parole chiave che Reddit mette in fondo o ai lati
            blacklist_keywords = ["share", "reply", "save", "comment", "award", "report", "vote"]
            
            lines = []
            for line in testo_markdown.splitlines():
                clean_line = line.strip()
                # Teniamo la riga solo se:
                # - Non è vuota
                # - È più lunga di 15 caratteri (evita "2 comments", "Share", ecc.)
                # - Non contiene esclusivamente parole social della blacklist
                if len(clean_line) > 15:
                    low_line = clean_line.lower()
                    if not any(word == low_line for word in blacklist_keywords):
                        lines.append(clean_line)

            dati["parsed_text"] = "\n\n".join(lines).strip()
        else:
            # Fallback se non troviamo il div specifico, usiamo il markdown di sistema pulito
            dati["parsed_text"] = result.markdown

        return dati