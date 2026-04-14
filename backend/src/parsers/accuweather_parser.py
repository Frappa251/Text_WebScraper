import asyncio
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def parse_accuweather_post(url: str) -> Dict[str, Any]:
    dominio = urlparse(url).netloc
    dati: Dict[str, Any] = {
        "url": url, 
        "domain": dominio, 
        "title": "", 
        "html_text": "", 
        "parsed_text": ""
    }

    # Manteniamo l'header standard per evitare blocchi
    headers_custom = {
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    browser_cfg = BrowserConfig(headless=True, headers=headers_custom)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success:
            return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        # 1. Estrazione del Titolo
        tag_titolo = soup.find("h1") or soup.find("title")
        titolo_testo = tag_titolo.get_text(strip=True) if tag_titolo else "AccuWeather Forecast"
        if "|" in titolo_testo:
            titolo_testo = titolo_testo.split("|")[0].strip()
        dati["title"] = titolo_testo

        # 2. Selezione dell'area principale robusta
        main_content = soup.find("div", class_="page-column-1") or \
                       soup.find("div", class_="two-column-page-content") or \
                       soup.find("div", class_="page-content") or \
                       soup.body

        if main_content:
            # 3. Pulizia di tutto il rumore visivo
            selectors_da_eliminare = [
                "nav", "footer", "header", "script", "style", "noscript",
                ".page-column-2", ".right-sidebar", 
                ".ad", ".ad-container", "[id^='ad-']", 
                ".breadcrumbs", ".policy-banner", ".banner-button",
                ".top-stories", ".featured-stories", ".around-the-globe",
                ".recent-locations", ".footer-wrap", ".footer-legals",
                "svg", "img" 
            ]
            
            for noisy in main_content.select(", ".join(selectors_da_eliminare)):
                noisy.decompose()

            # 4. Magia di Markdownify: Rimuove i tag dei link preservando il testo
            testo_markdown = md(str(main_content), heading_style="ATX", strip=['a', 'img'])

            # 5. Pulizia delle righe riga per riga per rimuovere le scritte in eccesso
            parsed_lines = []
            frasi_da_ignorare = [
                "Visualizza altro", 
                "Vedi tutto", 
                "Dati non supportati in questa posizione"
            ]
            
            for line in testo_markdown.splitlines():
                clean_line = line.strip()
                # Scartiamo le righe vuote, i rimasugli di markdown e le frasi inutili
                if clean_line and clean_line not in ["[", "]", "()", "[]", "!", "!()", "!\\[\\]\\(\\)"]:
                    if clean_line not in frasi_da_ignorare:
                        parsed_lines.append(clean_line)

            corpo_pulito = "\n".join(parsed_lines).strip()
            
            if titolo_testo:
                dati["parsed_text"] = f"# {titolo_testo}\n\n{corpo_pulito}"
            else:
                dati["parsed_text"] = corpo_pulito
                
        else:
            dati["parsed_text"] = result.markdown

        return dati