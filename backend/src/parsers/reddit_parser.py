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

    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success:
            return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        # 1. Estrazione del Titolo (spesso dentro shreddit-title o h1)
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

        parsed_lines = []
        
        # 3. Aggiungiamo esplicitamente il titolo come prima riga del testo parsato
        if titolo_testo:
            parsed_lines.append(titolo_testo)

        # 4. Elaborazione del contenuto principale
        if main_content:
            selectors_da_eliminare = [
                "button", "faceplate-hovercard", "shreddit-post-flair", 
                ".reward-button", "i", "svg", "aside"
            ]
            for noisy in main_content.select(", ".join(selectors_da_eliminare)):
                noisy.decompose()

            testo_markdown = md(str(main_content), heading_style="ATX")

            blacklist_keywords = ["share", "reply", "save", "comment", "award", "report", "vote"]
            
            for line in testo_markdown.splitlines():
                clean_line = line.strip()
                # Il filtro len > 15 potrebbe tagliare frasi brevi legittime.
                # Allentiamo il controllo: teniamo righe non vuote e non in blacklist
                if clean_line: 
                    low_line = clean_line.lower()
                    if not any(word == low_line for word in blacklist_keywords):
                        # Evitiamo di inserire stringhe composte solo da caratteri speciali residui
                        if any(c.isalpha() for c in clean_line):
                            parsed_lines.append(clean_line)

            dati["parsed_text"] = "\n\n".join(parsed_lines).strip()
        else:
            # Fallback
            dati["parsed_text"] = titolo_testo + "\n\n" + result.markdown if titolo_testo else result.markdown

        return dati