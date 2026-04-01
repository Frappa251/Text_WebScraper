import asyncio
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


def extract_wikipedia_main_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("span", class_="mw-page-title-main") or soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    main = soup.find("div", id="mw-content-text")
    if main is None:
        return ""

    # Rimuove elementi tipicamente rumorosi
    for selector in [
        "table.infobox",
        "table.sidebar",
        "table.navbox",
        "table.vertical-navbox",
        "table.metadata",
        "div.reflist",
        "div.navbox",
        "div.hatnote",
        "div.thumb",
        "div.sistersitebox",
        "sup.reference",
        "span.mw-editsection",
        "style",
        "script",
    ]:
        for tag in main.select(selector):
            tag.decompose()

    parts = []
    if title:
        parts.append(f"# {title}")

    # Tiene solo sezioni testuali rilevanti
    for elem in main.find_all(["p", "h2", "h3", "ul", "ol"], recursive=True):
        text = elem.get_text(" ", strip=True)
        if not text:
            continue

        # salta blocchi troppo corti o spazzatura frequente
        classes = elem.get("class", [])
        if "mw-empty-elt" in classes:
            continue

        parts.append(str(elem))

    cleaned_html = "\n".join(parts)
    return md(cleaned_html, heading_style="ATX")


async def _crawl_wikipedia(url: str) -> dict:
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)

        if not result.success:
            raise Exception(f"Crawl failed: {result.error_message}")

        html = result.html or ""
        parsed_markdown = extract_wikipedia_main_content(html)

        title = ""
        if hasattr(result, "metadata") and result.metadata:
            title = result.metadata.get("title", "")

        if title.endswith(" - Wikipedia"):
            title = title[:-12]

        return {
            "url": url,
            "domain": urlparse(url).netloc,
            "title": title,
            "html_text": html,
            "parsed_text": parsed_markdown,
        }


def parse_wikipedia(url: str) -> dict:
    return asyncio.run(_crawl_wikipedia(url))