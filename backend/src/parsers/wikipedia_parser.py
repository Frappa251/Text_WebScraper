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
    """Pulisce il markdown mantenendo una struttura leggibile."""
    # [testo](url) -> testo
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # rimuove enfasi markdown
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?m)^\s*[-*+]\s*", "", text)

    # rimuove righe-tabella markdown
    lines = []
    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            continue

        if re.fullmatch(r"[-|:\s]+", stripped):
            continue

        lines.append(stripped)

    return "\n\n".join(lines).strip()


def extract_wikipedia_main_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("span", class_="mw-page-title-main") or soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    main = soup.find("div", id="mw-content-text")
    if main is None:
        return ""

    # rimuove elementi rumorosi
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
        "div.shortdescription",
        "sup.reference",
        "span.mw-editsection",
        "style",
        "script",
        ".mw-jump-link",
        ".printfooter",
    ]:
        for tag in main.select(selector):
            tag.decompose()

    parts = [f"# {title}"] if title else []

    # prende il contenuto in ordine e si ferma prima delle sezioni finali rumorose
    for elem in main.find_all(["p", "h2", "h3"], recursive=True):
        text = elem.get_text(" ", strip=True)
        if not text:
            continue

        if elem.name in {"h2", "h3"}:
            section_title = text.replace("[edit]", "").strip()
            if section_title in STOP_SECTIONS:
                break
            parts.append(f"## {section_title}" if elem.name == "h2" else f"### {section_title}")
            continue

        # tiene solo paragrafi abbastanza informativi
        if len(text) < 40:
            continue

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