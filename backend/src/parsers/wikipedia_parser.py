import asyncio
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

def clean_wikipedia_markdown(text: str) -> str:
    """Rimuove i link del markdown [testo](url) lasciando solo 'testo'."""
    # Rimuove il formato [testo](url)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Rimuove eventuali doppie parentesi quadre residue o spazi eccessivi
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_wikipedia_main_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("span", class_="mw-page-title-main") or soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    main = soup.find("div", id="mw-content-text")
    if main is None: return ""

    for selector in [
        "table.infobox", "table.sidebar", "table.navbox", "table.vertical-navbox",
        "table.metadata", "div.reflist", "div.navbox", "div.hatnote",
        "div.thumb", "div.sistersitebox", "sup.reference", "span.mw-editsection",
        "style", "script", ".mw-jump-link", ".printfooter"
    ]:
        for tag in main.select(selector):
            tag.decompose()

    parts = [f"# {title}"] if title else []
    for elem in main.find_all(["p", "h2", "h3", "ul", "ol"]):
        if not elem.get_text(strip=True): continue
        parts.append(str(elem))

    raw_md = md("\n".join(parts), heading_style="ATX")
    return clean_wikipedia_markdown(raw_md)

async def parse_wikipedia_post(url: str) -> dict:
    """Versione ASYNC corretta per il server."""
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success: return {}

        parsed_markdown = extract_wikipedia_main_content(result.html)
        
        # Recupero titolo pulito
        soup = BeautifulSoup(result.html, "html.parser")
        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Wikipedia Page"
        if title.endswith(" - Wikipedia"): title = title[:-12]

        return {
            "url": url,
            "domain": urlparse(url).netloc,
            "title": title,
            "html_text": result.html,
            "parsed_text": parsed_markdown,
        }