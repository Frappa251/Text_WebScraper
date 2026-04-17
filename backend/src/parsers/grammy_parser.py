import re
import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = logging.getLogger(__name__)


EXACT_NOISE_TEXT = {
    "read more",
    "subscribe to newsletters",
    "join us on social",
    "related",
    "latest news",
    "you may also like",
    "facebook",
    "twitter",
    "email",
    "e-mail",
    "music news",
    "feature",
    "news",
}

STOP_TEXT_PATTERNS = [
    r"^read more$",
    r"^related$",
    r"^latest news$",
    r"^you may also like$",
    r"^more from$",
    r"^recommended$",
]

NOISE_TEXT_PATTERNS = [
    r"^photo:\s*",
    r"^graphic courtesy",
    r"^all photos courtesy",
    r"^follow .*",
    r"^share this.*",
    r"^advertisement$",
    r"^sign up.*",
    r".*newsletter.*",
    r"^more from.*",
    r"^related.*",
    r"^latest news.*",
]

NOISY_CONTAINER_HINTS = [
    "related",
    "promo",
    "card",
    "teaser",
    "recommended",
    "share",
    "social",
    "newsletter",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_grammy_markdown(text: str) -> str:
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)

    cleaned_lines = []
    prev_blank = False

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.lower() in EXACT_NOISE_TEXT:
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


def normalize_attrs(tag: Tag) -> str:
    values = []

    classes = tag.get("class", [])
    if isinstance(classes, list):
        values.extend(str(c) for c in classes if c is not None)
    elif classes:
        values.append(str(classes))

    for attr in ["id", "role", "aria-label", "data-testid"]:
        value = tag.get(attr)
        if value is not None:
            values.append(str(value))

    return " ".join(values).lower()


def is_noise_text(text: str) -> bool:
    t = normalize_text(text).lower()
    if not t:
        return True

    if t in EXACT_NOISE_TEXT:
        return True

    return any(re.search(p, t, re.IGNORECASE) for p in NOISE_TEXT_PATTERNS)


def is_stop_text(text: str) -> bool:
    t = normalize_text(text).lower()
    return any(re.search(p, t, re.IGNORECASE) for p in STOP_TEXT_PATTERNS)


def looks_like_new_article_title(text: str) -> bool:
    t = normalize_text(text)
    lower = t.lower()

    if len(t) < 20 or len(t) > 160:
        return False

    if t.endswith("."):
        return False

    # titolo di altro articolo: tipicamente con pipe
    if "|" in t:
        return True

    # formule da card/promozione/editorial link
    promo_patterns = [
        r"^watch ",
        r"^listen to ",
        r"^see the full ",
        r"^read: ",
        r"^exclusive: ",
    ]
    if any(re.search(p, lower, re.IGNORECASE) for p in promo_patterns):
        return True

    return False


def is_probable_teaser(tag: Tag, text: str) -> bool:
    attrs = normalize_attrs(tag)
    if any(hint in attrs for hint in NOISY_CONTAINER_HINTS):
        return True

    link_count = len(tag.find_all("a"))
    text_len = len(text)

    if link_count >= 3 and text_len < 180:
        return True

    if tag.name == "p" and text_len < 120 and looks_like_new_article_title(text):
        return True

    return False


def remove_global_noise(soup: BeautifulSoup) -> None:
    for selector in [
        "script", "style", "noscript", "iframe", "svg", "form",
        "button", "nav", "footer", "aside"
    ]:
        for tag in soup.select(selector):
            tag.decompose()


def find_title_tag(soup: BeautifulSoup) -> Tag | None:
    return soup.find("h1")


def extract_following_blocks_from_title(title_tag: Tag, is_roundup: bool = False) -> list[str]:
    parts = []
    seen_html = set()
    started = False
    valid_p_count = 0
    bad_streak = 0

    title_text = normalize_text(title_tag.get_text(" ", strip=True))

    for elem in title_tag.next_elements:
        if not isinstance(elem, Tag):
            continue

        if elem is title_tag:
            continue

        if elem.name not in {"p", "h2", "h3", "h4", "li"}:
            continue

        text = normalize_text(elem.get_text(" ", strip=True))
        if not text:
            continue

        if text == title_text:
            continue

        if not is_roundup and started and valid_p_count >= 3 and looks_like_new_article_title(text):
            break

        if is_stop_text(text):
            break

        if is_noise_text(text):
            bad_streak += 1
            if started and bad_streak >= 2:
                break
            continue

        if elem.name in {"h2", "h3", "h4"}:
            if len(text) >= 8:
                norm_html = re.sub(r"\s+", " ", str(elem).strip())
                if norm_html not in seen_html:
                    parts.append(str(elem))
                    seen_html.add(norm_html)
                    started = True
                    bad_streak = 0
            continue

        if elem.name == "li":
            if len(text) < 8:
                bad_streak += 1
                if started and bad_streak >= 2:
                    break
                continue

            norm_html = re.sub(r"\s+", " ", str(elem).strip())
            if norm_html not in seen_html:
                parts.append(str(elem))
                seen_html.add(norm_html)
                started = True
                bad_streak = 0
            continue

        if elem.name == "p":
            min_len = 25 if is_roundup else 30

            if len(text) < min_len:
                bad_streak += 1
                if started and bad_streak >= 2:
                    break
                continue

            if is_probable_teaser(elem, text):
                bad_streak += 1
                if started and bad_streak >= 2:
                    break
                continue

            norm_html = re.sub(r"\s+", " ", str(elem).strip())
            if norm_html not in seen_html:
                parts.append(str(elem))
                seen_html.add(norm_html)
                started = True
                bad_streak = 0
                valid_p_count += 1

    return parts


def deduplicate_by_text(html_parts: list[str]) -> list[str]:
    seen_texts = set()
    result = []

    for part in html_parts:
        soup = BeautifulSoup(part, "html.parser")
        text = normalize_text(soup.get_text(" ", strip=True))
        if text in seen_texts:
            continue
        seen_texts.add(text)
        result.append(part)

    return result


def is_roundup_article(url: str, title: str) -> bool:
    url_l = url.lower()
    title_l = title.lower()

    roundup_hints = [
        "new music friday",
        "listen to songs",
        "albums from",
        "songs & albums from",
        "best new songs",
        "best new albums",
    ]

    return any(h in url_l for h in roundup_hints) or any(h in title_l for h in roundup_hints)


def extract_grammy_main_content(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    remove_global_noise(soup)

    title_tag = find_title_tag(soup)
    if title_tag is None:
        return ""

    title = normalize_text(title_tag.get_text(" ", strip=True))
    roundup = is_roundup_article(url, title)

    parts = [f"# {title}"] if title else []

    body_parts = extract_following_blocks_from_title(title_tag, is_roundup=roundup)
    body_parts = deduplicate_by_text(body_parts)
    parts.extend(body_parts)

    raw_md = md("\n".join(parts), heading_style="ATX", strip=["a", "img"]) if parts else ""
    return clean_grammy_markdown(raw_md)

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

            parsed_markdown = extract_grammy_main_content(html, url) or ""

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("h1")
            title = normalize_text(title_tag.get_text(" ", strip=True)) if title_tag else "GRAMMY Page"

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