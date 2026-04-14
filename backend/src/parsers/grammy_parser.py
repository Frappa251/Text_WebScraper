import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md


SOCIAL_LABELS = {"facebook", "twitter", "email", "e-mail"}
NOISE_PATTERNS = [
    r"read more",
    r"watch highlights",
    r"subscribe",
    r"newsletter",
    r"grammy shop",
    r"login",
]


def clean_markdown(text: str) -> str:
    if not text:
        return ""

    # rimuove link markdown: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # rimuove immagini markdown
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)

    # normalizza spazi
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # rimuove simboli isolati frequenti
    text = re.sub(r"^[>*\-\s]+$", "", text, flags=re.MULTILINE)

    return text.strip()


def is_noise_text(text: str) -> bool:
    if not text:
        return True

    normalized = text.strip().lower()
    if normalized in SOCIAL_LABELS:
        return True

    return any(re.search(pattern, normalized) for pattern in NOISE_PATTERNS)


def remove_noise(soup: BeautifulSoup) -> None:
    # tag inutili
    for tag in soup.select("script, style, noscript, iframe, svg, form, button"):
        tag.decompose()

    # elementi spesso rumorosi per classe/id/aria-label
    noisy_keywords = [
        "share", "social", "related", "promo", "newsletter",
        "subscribe", "advert", "ad-", "banner", "nav", "footer",
        "header", "breadcrumb", "cookie", "modal", "popup"
    ]

    for tag in soup.find_all(True):
        attrs = " ".join(
            str(v) for k, v in tag.attrs.items()
            if k in {"class", "id", "aria-label", "role", "data-testid"}
        ).lower()

        if any(k in attrs for k in noisy_keywords):
            tag.decompose()
            continue

        # elimina elementi brevissimi tipici di UI/social
        text = tag.get_text(" ", strip=True)
        if text and len(text) < 30 and is_noise_text(text):
            tag.decompose()


def find_main_content(soup: BeautifulSoup) -> Tag | None:
    # tentativi progressivi
    candidates = [
        "main",
        "article",
        "[role='main']",
        ".article",
        ".article-body",
        ".node__content",
        ".field--name-body",
    ]

    for sel in candidates:
        node = soup.select_one(sel)
        if node:
            return node

    # fallback: prendi il contenitore con più paragrafi
    best_node = None
    best_score = -1

    for node in soup.find_all(["div", "section", "article", "main"]):
        p_count = len(node.find_all("p"))
        text_len = len(node.get_text(" ", strip=True))
        score = p_count * 50 + text_len
        if p_count >= 3 and score > best_score:
            best_score = score
            best_node = node

    return best_node


def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)

    if soup.title:
        return soup.title.get_text(" ", strip=True)

    return ""


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def parse_grammy(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = extract_title(soup)

    remove_noise(soup)
    main = find_main_content(soup)

    if not main:
        parsed_text = ""
    else:
        # tieni solo i tag editoriali utili
        allowed = []
        for node in main.find_all(["h1", "h2", "h3", "p", "ul", "ol", "li"]):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            if is_noise_text(text):
                continue
            allowed.append(str(node))

        content_html = "\n".join(allowed)
        parsed_text = clean_markdown(md(content_html))

    return {
        "url": url,
        "domain": extract_domain(url),
        "title": title,
        "parsed_text": parsed_text,
    }