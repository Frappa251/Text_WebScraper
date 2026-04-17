import re
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

class WikipediaParser:
    """Classe dedicata all'estrazione e pulizia degli articoli dal dominio Wikipedia."""

    @staticmethod
    def clean_wikipedia_markdown(text: str) -> str:
        """Pulisce il markdown generato rimuovendo link e spaziature extra."""
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = text.replace("**", "").replace("__", "")
        cleaned = []
        prev_blank = False
        for line in text.splitlines():
            stripped = line.rstrip()
            if not stripped:
                if not prev_blank:
                    cleaned.append("")
                prev_blank = True
                continue
            cleaned.append(stripped)
            prev_blank = False
        return "\n".join(cleaned).strip()

    @staticmethod
    def extract_wikipedia_main_content(html: str) -> str:
        """Estrae il contenuto testuale ignorando tabelle laterali e riferimenti."""
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("span", class_="mw-page-title-main") or soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""

        main = soup.select_one("div#mw-content-text div.mw-parser-output")
        if main is None:
            main = soup.find("div", id="mw-content-text")
        if main is None:
            return ""

        for selector in [
            "table.infobox", "table.sidebar", "table.navbox", "table.vertical-navbox",
            "table.metadata", "div.reflist", "div.navbox", "div.hatnote", "div.thumb",
            "div.sistersitebox", "sup.reference", "span.mw-editsection", "style", "script",
            ".mw-jump-link", ".printfooter"
        ]:
            for tag in main.select(selector):
                tag.decompose()

        is_disambiguation = "may refer to" in soup.get_text(" ", strip=True).lower()
        has_data_table = len(main.select("table.wikitable")) > 0

        parts = [f"# {title}"] if title else []
        stop_sections = {"See also", "References", "External links", "Further reading", "Notes", "Bibliography", "Sources"}

        if is_disambiguation:
            elements = main.find_all(["p", "ul", "ol", "dl"])
        elif has_data_table:
            elements = main.find_all(["p", "h2", "h3", "h4", "ul", "ol", "dl", "table"])
        else:
            elements = main.find_all(["p", "h2", "h3", "h4", "ul", "ol", "dl"])

        for elem in elements:
            text = elem.get_text(" ", strip=True)
            if not text:
                continue

            if elem.name in ["h2", "h3", "h4"]:
                section_title = text.replace("[edit]", "").strip()
                if section_title in stop_sections:
                    break
                parts.append(str(elem))
                continue

            if elem.name == "p":
                if not is_disambiguation and len(text) < 40:
                    continue
                parts.append(str(elem))
                continue

            if elem.name in ["ul", "ol", "dl"]:
                parts.append(str(elem))
                continue

            if elem.name == "table" and "wikitable" in (elem.get("class") or []):
                table_lines = []
                for row in elem.select("tr"):
                    cells = [c.get_text(" ", strip=True) for c in row.select("th, td")]
                    cells = [c for c in cells if c]
                    if cells:
                        table_lines.append(" | ".join(cells))
                if table_lines:
                    parts.append("<p>" + "</p><p>".join(table_lines) + "</p>")
                continue

        raw_md = md("\n".join(parts), heading_style="ATX")
        return WikipediaParser.clean_wikipedia_markdown(raw_md)

    async def parse(self, url: str) -> Dict[str, Any]:
        """Metodo principale che scarica e formatta la pagina di Wikipedia."""
        browser_cfg = BrowserConfig(headless=True)
        run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            if not result.success:
                return {}

            html = result.html or ""
            parsed_markdown = self.extract_wikipedia_main_content(html)

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("span", class_="mw-page-title-main") or soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else "Wikipedia Page"

            return {
                "url": url,
                "domain": urlparse(url).netloc,
                "title": title,
                "html_text": html,
                "parsed_text": parsed_markdown,
            }