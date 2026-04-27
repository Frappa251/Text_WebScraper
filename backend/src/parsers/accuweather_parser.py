import asyncio
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

class AccuweatherParser:
    """Classe dedicata all'estrazione e pulizia delle previsioni da AccuWeather."""

    async def parse(self, url: str) -> Dict[str, Any]:
        """
        Scarica e pulisce la pagina meteo rimuovendo layout grafici e pubblicità.

        Args:
            url (str): L'URL della pagina web da parsare.

        Returns:
            Dict[str, Any]: Un dizionario contenente URL, dominio, titolo, HTML grezzo 
                            e testo parsato in formato Markdown.
        """
        dominio = urlparse(url).netloc
        dati: Dict[str, Any] = {
            "url": url,
            "domain": dominio,
            "title": "",
            "html_text": "",
            "parsed_text": ""
        }

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

            tag_titolo = soup.find("h1") or soup.find("title")
            titolo_testo = tag_titolo.get_text(strip=True) if tag_titolo else "AccuWeather Forecast"
            if "|" in titolo_testo:
                titolo_testo = titolo_testo.split("|")[0].strip()
            dati["title"] = titolo_testo

            main_content = soup.find("div", class_="page-column-1") or \
                           soup.find("div", class_="two-column-page-content") or \
                           soup.find("div", class_="page-content") or \
                           soup.body

            if main_content:
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

                testo_markdown = md(str(main_content), heading_style="ATX", strip=['a', 'img'])

                parsed_lines = []
                frasi_da_ignorare = ["Visualizza altro", "Vedi tutto", "Dati non supportati in questa posizione"]

                for line in testo_markdown.splitlines():
                    clean_line = line.strip()
                    if clean_line and clean_line not in ["[", "]", "()", "[]", "!", "!()", "!\\[\\]\\(\\)"]:
                        if clean_line not in frasi_da_ignorare:
                            parsed_lines.append(clean_line)

                corpo_pulito = "\n".join(parsed_lines).strip()
                dati["parsed_text"] = f"# {titolo_testo}\n\n{corpo_pulito}" if titolo_testo else corpo_pulito
            else:
                dati["parsed_text"] = result.markdown

            return dati

    async def parse_html(self, url: str, html_text: str) -> Dict[str, Any]:
        """
        Esegue il parsing di HTML diretto mantenendo la stessa logica di pulizia, 
        senza effettuare il crawling della pagina.

        Args:
            url (str): L'URL originale della pagina web.
            html_text (str): Il codice HTML grezzo da cui estrarre il testo.

        Returns:
            Dict[str, Any]: Un dizionario contenente URL, dominio, titolo, HTML grezzo 
                            e testo parsato in formato Markdown.
        """
        dominio = urlparse(url).netloc
        dati: Dict[str, Any] = {
            "url": url,
            "domain": dominio,
            "title": "",
            "html_text": html_text,
            "parsed_text": ""
        }

        soup = BeautifulSoup(html_text, "html.parser")

        tag_titolo = soup.find("h1") or soup.find("title")
        titolo_testo = tag_titolo.get_text(strip=True) if tag_titolo else "AccuWeather Forecast"
        if "|" in titolo_testo:
            titolo_testo = titolo_testo.split("|")[0].strip()
        dati["title"] = titolo_testo

        main_content = soup.find("div", class_="page-column-1") or \
                       soup.find("div", class_="two-column-page-content") or \
                       soup.find("div", class_="page-content") or \
                       soup.body

        if main_content:
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

            testo_markdown = md(str(main_content), heading_style="ATX", strip=['a', 'img'])

            parsed_lines = []
            frasi_da_ignorare = ["Visualizza altro", "Vedi tutto", "Dati non supportati in questa posizione"]

            for line in testo_markdown.splitlines():
                clean_line = line.strip()
                if clean_line and clean_line not in ["[", "]", "()", "[]", "!", "!()", "!\\[\\]\\(\\)"]:
                    if clean_line not in frasi_da_ignorare:
                        parsed_lines.append(clean_line)

            corpo_pulito = "\n".join(parsed_lines).strip()
            dati["parsed_text"] = f"# {titolo_testo}\n\n{corpo_pulito}" if titolo_testo else corpo_pulito
        else:
            dati["parsed_text"] = ""

        return dati