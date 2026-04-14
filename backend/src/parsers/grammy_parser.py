import re
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = logging.getLogger(__name__)

def clean_grammy_markdown(text: str) -> str:
    """
    Pulisce il markdown finale da residui di formattazione 
    e righe inutili isolate.
    """
    text = text.replace("**", "").replace("__", "")

    cleaned_lines = []
    prev_blank = False

    for line in text.splitlines():
        stripped = line.strip()

        # Salta le righe con parole singole inutili sfuggite al parser
        if stripped.lower() in {
            "facebook", "twitter", "email", "e-mail",
            "music news", "feature", "news"
        }:
            continue

        if not stripped:
            if not prev_blank:
                cleaned_lines.append("")
            prev_blank = True
            continue

        cleaned_lines.append(stripped)
        prev_blank = False

    # Assicura che ci siano al massimo doppi a capo
    text = "\n".join(cleaned_lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def find_grammy_main_content(soup: BeautifulSoup):
    """
    Individua il contenitore principale dell'articolo.
    """
    for selector in ["article", "main article", "main", "[role='main']"]:
        node = soup.select_one(selector)
        if node:
            return node

    best = None
    best_score = -1

    # Fallback euristico se mancano i tag semantici
    for node in soup.find_all(["div", "section"]):
        p_count = len(node.find_all("p", recursive=False))
        h_count = len(node.find_all(["h2", "h3"], recursive=False))
        text_len = len(node.get_text(" ", strip=True))

        score = (p_count * 80) + (h_count * 30) + text_len
        if p_count >= 3 and score > best_score:
            best = node
            best_score = score

    return best

def cut_off_infinite_scroll(main_node: BeautifulSoup) -> None:
    """
    Trova i divisori tipici di fine articolo e distrugge tutto il contenuto successivo,
    prevenendo l'ingestione di articoli correlati o scroll infinito.
    """
    cutoff_phrases = [
        "latest news & exclusive videos",
        "explore the world of",
        "read list",
        "you may also like",
        "latest news"
    ]
    
    for tag in main_node.find_all(['h2', 'h3', 'div', 'section']):
        text = tag.get_text(" ", strip=True).lower()
        
        if any(phrase in text for phrase in cutoff_phrases) or text == "read more":
            # Trova l'elemento di blocco di alto livello sotto 'main'
            # per tagliare il ramo corretto senza lasciare rimasugli
            parent_under_main = tag
            while parent_under_main.parent and parent_under_main.parent != main_node:
                parent_under_main = parent_under_main.parent
            
            # Distruggi i fratelli successivi
            for sibling in parent_under_main.find_next_siblings():
                sibling.decompose()
            
            # Distruggi il blocco che contiene la frase di stop
            parent_under_main.decompose()
            break

def remove_grammy_noise(main: BeautifulSoup) -> None:
    """
    Pulisce il contenitore principale da pubblicità, menu e popup.
    """
    # 1. Rimuove tag spazzatura di default
    for selector in ["script", "style", "noscript", "iframe", "svg", "form", "button", "nav", "footer", "aside", "figure"]:
        for tag in main.select(selector):
            tag.decompose()

    # 2. Rimuove blocchi basati su classi/ID che indicano pubblicità o social
    noise_classes = ["newsletter", "share", "social", "promo", "advertisement", "related-articles"]
    
    for tag in main.find_all(True):
        classes = tag.get("class", [])
        class_str = " ".join(classes).lower() if isinstance(classes, list) else str(classes).lower()
        id_str = str(tag.get("id", "")).lower()

        if any(nc in class_str or nc in id_str for nc in noise_classes):
            tag.decompose()
            continue

        # 3. Rimuove paragrafi che contengono ESATTAMENTE frasi di stop (evita falsi positivi)
        text = tag.get_text(" ", strip=True).lower()
        if text in ["subscribe to newsletters", "join us on social", "related"]:
            tag.decompose()

def extract_grammy_main_content(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    main = find_grammy_main_content(soup)
    if main is None:
        return ""

    # 1. Pulisce il contenitore dal rumore
    remove_grammy_noise(main)
    
    # 2. Amputa l'infinite scroll e le liste di "read more" alla fine
    cut_off_infinite_scroll(main)

    # 3. Genera Markdown intero (strip=['a', 'img'] pulisce nativamente link e foto)
    raw_md = md(str(main), heading_style="ATX", strip=['a', 'img'])
    
    clean_md = clean_grammy_markdown(raw_md)

    if title:
        return f"# {title}\n\n{clean_md}"
    
    return clean_md

async def parse_grammy_post(url: str) -> dict:
    try:
        browser_cfg = BrowserConfig(headless=True)
        run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            if not result.success:
                logger.warning(f"Crawl failed for {url}: {result}")
                return {}

            html = result.html or ""
            if not html.strip():
                logger.warning(f"Empty HTML for {url}")
                return {}
                
            parsed_markdown = extract_grammy_main_content(html, url)
            parsed_markdown = parsed_markdown if parsed_markdown else ""

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else "GRAMMY Page"

            return {
                "url": url,
                "domain": urlparse(url).netloc,
                "title": title,
                "html_text": html,
                "parsed_text": parsed_markdown,
            }
    except Exception as e:
        logger.error(f"Error parsing Grammy URL {url}: {str(e)}", exc_info=True)
        return {}