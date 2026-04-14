import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


STOP_PHRASES = {
    "Read More",
    "Subscribe to Newsletters",
    "Join us on Social",
}

STOP_SECTION_PATTERNS = [
    r"related",
    r"read more",
    r"more from",
    r"latest news",
    r"you may also like",
]


def clean_grammy_markdown(text: str) -> str:
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = text.replace("**", "").replace("__", "")

    cleaned_lines = []
    prev_blank = False

    for line in text.splitlines():
        stripped = line.strip()

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

    text = "\n".join(cleaned_lines).strip()

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_probable_roundup(url: str, soup: BeautifulSoup, main) -> bool:
    url_l = url.lower()
    if "new-music-friday" in url_l:
        return True

    h2_h3_count = len(main.find_all(["h2", "h3"])) if main else 0
    p_count = len(main.find_all("p")) if main else 0
    list_count = len(main.find_all(["ul", "ol"])) if main else 0

    return (h2_h3_count >= 4 and list_count >= 1) or (h2_h3_count >= 6 and p_count >= 6)


def is_probable_awards_list(url: str, soup: BeautifulSoup, main) -> bool:
    url_l = url.lower()
    keywords = ["winners", "nominees", "see-the-full", "full-winners"]
    if any(k in url_l for k in keywords):
        return True

    page_text = soup.get_text(" ", strip=True).lower()
    return "nominees" in page_text and "winners" in page_text


def find_grammy_main_content(soup: BeautifulSoup):
    for selector in [
        "article",
        "main article",
        "main",
        "[role='main']",
    ]:
        node = soup.select_one(selector)
        if node:
            return node

    best = None
    best_score = -1

    for node in soup.find_all(["div", "section"]):
        p_count = len(node.find_all("p"))
        h_count = len(node.find_all(["h2", "h3"]))
        text_len = len(node.get_text(" ", strip=True))

        score = (p_count * 80) + (h_count * 30) + text_len
        if p_count >= 3 and score > best_score:
            best = node
            best_score = score

    return best


def remove_grammy_noise(main: BeautifulSoup) -> None:
    for selector in [
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "form",
        "button",
        "nav",
        "footer",
        "aside",
        "figure figcaption",  
    ]:
        for tag in main.select(selector):
            tag.decompose()

    noisy_attr_keywords = [
        "share",
        "social",
        "newsletter",
        "subscribe",
        "related",
        "promo",
        "advert",
        "ad-",
        "outbrain",
        "taboola",
        "breadcrumb",
        "footer",
        "header",
        "nav",
    ]

    for tag in main.find_all(True):
        attrs = " ".join(
            str(v) for k, v in tag.attrs.items()
            if k in {"class", "id", "role", "aria-label", "data-testid"}
        ).lower()

        if any(k in attrs for k in noisy_attr_keywords):
            tag.decompose()
            continue

        text = tag.get_text(" ", strip=True)
        if text in STOP_PHRASES:
            tag.decompose()


def extract_grammy_main_content(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    main = find_grammy_main_content(soup)
    if main is None:
        return ""

    remove_grammy_noise(main)

    is_roundup = is_probable_roundup(url, soup, main)
    is_awards = is_probable_awards_list(url, soup, main)

    parts = [f"# {title}"] if title else []

    if title_tag:
        for sib in title_tag.find_next_siblings():
            if sib.name in ["p", "div"]:
                text = sib.get_text(" ", strip=True)
                if text and len(text) > 40:
                    parts.append(str(sib))
                    break

    if is_awards:
        allowed_tags = ["p", "h2", "h3", "h4", "ul", "ol", "dl"]
    elif is_roundup:
        allowed_tags = ["p", "h2", "h3", "h4", "ul", "ol"]
    else:
        allowed_tags = ["p", "h2", "h3", "h4", "ul", "ol"]

    elements = main.find_all(allowed_tags)

    for elem in elements:
        text = elem.get_text(" ", strip=True)
        if not text:
            continue

        if any(re.search(pattern, text, re.IGNORECASE) for pattern in STOP_SECTION_PATTERNS):
            break

        if elem.name in ["h2", "h3", "h4"]:
            parts.append(str(elem))
            continue

        if elem.name == "p":
            min_len = 25 if is_roundup or is_awards else 40
            if len(text) < min_len:
                continue

            lower = text.lower()
            if lower in {"facebook", "twitter", "email", "e-mail"}:
                continue
            if "grammys/" in lower:
                continue

            parts.append(str(elem))
            continue

        if elem.name in ["ul", "ol", "dl"]:
            parts.append(str(elem))
            continue

    raw_md = md("\n".join(parts), heading_style="ATX")
    return clean_grammy_markdown(raw_md)


async def parse_grammy_post(url: str) -> dict:
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success:
            return {}

        html = result.html or ""
        parsed_markdown = extract_grammy_main_content(html, url)

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