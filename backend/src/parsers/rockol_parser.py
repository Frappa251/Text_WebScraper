import asyncio
import re
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

class RockolParser:
    """Classe dedicata all'estrazione e pulizia degli articoli dal dominio Rockol.it."""

    async def parse(self, url: str) -> Dict[str, Any]:
        """
        Esegue il crawling dell'URL specificato, individua il contenuto principale,
        rimuove gli elementi di disturbo e restituisce il testo in formato Markdown.

        Args:
            url (str): URL passato alla funzione

        Returns:
            Dict[str, Any]: Dizionario con chiave gli elementi per la risposta del parser
        """
        dominio = urlparse(url).netloc
        dati: Dict[str, Any] = {
            "url": url,
            "domain": dominio,
            "title": "",
            "html_text": "",
            "parsed_text": ""
        }

        headers_it = {"Accept-Language": "it-IT,it;q=0.9"}
        browser_cfg = BrowserConfig(headless=True, headers=headers_it)
        run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            if not result.success:
                return dati

            dati["html_text"] = result.html
            soup = BeautifulSoup(result.html, "html.parser")

            tag_titolo = soup.find("h1")
            dati["title"] = tag_titolo.get_text(strip=True) if tag_titolo else "Titolo non trovato"

            main_content = (
                soup.find("div", itemprop="articleBody") or
                soup.find("div", class_="article-body") or
                soup.find("div", class_="testo-articolo") or
                soup.find("article") or
                soup.find("div", class_="article-text") or
                soup.find("div", class_="main-content") or
                soup.find("div", id="content") or
                soup.body
            )

            if main_content:
                selectors_da_eliminare = [
                    "h1",
                    "img", "figure", "picture",
                    ".related-box", ".correlati", ".related",
                    ".social-share", ".social-buttons",
                    "script", "style", "iframe",
                    ".adv", ".advertising", ".banner",
                    ".tags-container",
                    ".artist-menu", ".artist-nav",
                    ".breadcrumbs", ".video-ros",
                    "header", "footer"
                ]

                for selector in selectors_da_eliminare:
                    for element in main_content.select(selector):
                        element.decompose()

                testo_markdown = md(str(main_content), heading_style="ATX")

                parsed_lines = []
                if dati["title"]:
                    parsed_lines.append(f"# {dati['title']}")

                for line in testo_markdown.splitlines():
                    clean_line = line.strip()

                    if ("Ultimissime" in clean_line and clean_line.startswith("#")) or clean_line.startswith("Schede:"):
                        break

                    if clean_line.startswith("[Notizie]") or "Torna all'homepage" in clean_line or "[Biografia]" in clean_line or "[Articoli]" in clean_line:
                        continue

                    if "©" in clean_line or "Riproduzione riservata" in clean_line or clean_line.startswith("La fotografia dell'articolo"):
                        continue

                    if clean_line.startswith("Di ") and "[" in clean_line:
                        match = re.search(r'\[(.*?)\]', clean_line)
                        if match:
                            clean_line = f"*Di {match.group(1)}*"

                    if clean_line.startswith("](") or clean_line.endswith("]("):
                        continue

                    if clean_line and any(c.isalpha() for c in clean_line):
                        clean_line = re.sub(r'\[\s*\]\([^)]+\)', '', clean_line).strip()
                        if len(clean_line) > 2:
                            parsed_lines.append(clean_line)

                dati["parsed_text"] = "\n\n".join(parsed_lines).strip()

            return dati

    async def parse_html(self, url: str, html_text: str) -> Dict[str, Any]:
        """
        Esegue il parsing di html_text diretto mantenendo la stessa logica del parse standard.
        """
        dominio = urlparse(url).netloc
        dati: Dict[str, Any] = {
            "url": url,
            "domain": dominio,
            "title": "",
            "html_text": html_text,
            "parsed_text": ""
        }

        if not html_text.strip():
            return dati

        soup = BeautifulSoup(html_text, "html.parser")

        tag_titolo = soup.find("h1")
        dati["title"] = tag_titolo.get_text(strip=True) if tag_titolo else "Titolo non trovato"

        main_content = (
            soup.find("div", itemprop="articleBody") or
            soup.find("div", class_="article-body") or
            soup.find("div", class_="testo-articolo") or
            soup.find("article") or
            soup.find("div", class_="article-text") or
            soup.find("div", class_="main-content") or
            soup.find("div", id="content") or
            soup.body
        )

        if main_content:
            selectors_da_eliminare = [
                "h1",
                "img", "figure", "picture",
                ".related-box", ".correlati", ".related",
                ".social-share", ".social-buttons",
                "script", "style", "iframe",
                ".adv", ".advertising", ".banner",
                ".tags-container",
                ".artist-menu", ".artist-nav",
                ".breadcrumbs", ".video-ros",
                "header", "footer"
            ]

            for selector in selectors_da_eliminare:
                for element in main_content.select(selector):
                    element.decompose()

            testo_markdown = md(str(main_content), heading_style="ATX")

            parsed_lines = []
            if dati["title"]:
                parsed_lines.append(f"# {dati['title']}")

            for line in testo_markdown.splitlines():
                clean_line = line.strip()

                if ("Ultimissime" in clean_line and clean_line.startswith("#")) or clean_line.startswith("Schede:"):
                    break

                if clean_line.startswith("[Notizie]") or "Torna all'homepage" in clean_line or "[Biografia]" in clean_line or "[Articoli]" in clean_line:
                    continue

                if "©" in clean_line or "Riproduzione riservata" in clean_line or clean_line.startswith("La fotografia dell'articolo"):
                    continue

                if clean_line.startswith("Di ") and "[" in clean_line:
                    match = re.search(r'\[(.*?)\]', clean_line)
                    if match:
                        clean_line = f"*Di {match.group(1)}*"

                if clean_line.startswith("](") or clean_line.endswith("]("):
                    continue

                if clean_line and any(c.isalpha() for c in clean_line):
                    clean_line = re.sub(r'\[\s*\]\([^)]+\)', '', clean_line).strip()
                    if len(clean_line) > 2:
                        parsed_lines.append(clean_line)

            dati["parsed_text"] = "\n\n".join(parsed_lines).strip()

        return dati