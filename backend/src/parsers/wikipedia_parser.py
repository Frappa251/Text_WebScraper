import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


STOP_SECTIONS = {
    "See also",
    "References",
    "External links",
    "Further reading",
    "Notes",
    "Sources",
    "Bibliography",
}


def clean_wikipedia_markdown(text: str) -> str:
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = text.replace("**", "").replace("__", "")

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # NON rimuovere le righe tabella, servono per le list pages
        lines.append(stripped)

    return "\n\n".join(lines).strip()


def extract_wikipedia_main_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("span", class_="mw-page-title-main") or soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    main = soup.find("div", id="mw-content-text")
    if main is None:
        return ""

    # rimuovi solo tabelle decorative, NON le wikitable dati
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
        ".mw-jump-link",
        ".printfooter"
    ]:
        for tag in main.select(selector):
            tag.decompose()

    # disambiguation
    is_disambiguation = "may refer to" in soup.get_text(" ", strip=True).lower()

    # list/table page
    has_data_table = len(main.select("table.wikitable")) > 0

    parts = [f"# {title}"] if title else []

    stop_sections = {
        "See also",
        "References",
        "External links",
        "Further reading",
        "Notes",
        "Bibliography",
        "Sources",
    }

    if is_disambiguation:
        elements = main.find_all(["p", "ul"])
    elif has_data_table:
        elements = main.find_all(["p", "h2", "h3", "table"])
    else:
        elements = main.find_all(["p", "h2", "h3"])

    for elem in elements:
        text = elem.get_text(" ", strip=True)
        if not text:
            continue

        if elem.name in ["h2", "h3"]:
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

        if elem.name == "ul" and is_disambiguation:
            parts.append(str(elem))
            continue

        if elem.name == "table" and "wikitable" in (elem.get("class") or []):
            parts.append(str(elem))

    raw_md = md("\n".join(parts), heading_style="ATX")
    return clean_wikipedia_markdown(raw_md)


async def parse_wikipedia_post(url: str) -> dict:
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success:
            return {}

        html = result.html or ""
        parsed_markdown = extract_wikipedia_main_content(html)

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