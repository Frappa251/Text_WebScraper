import re
import logging
from urllib.parse import urlparse
from typing import Dict, Any

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = logging.getLogger(__name__)

EXACT_NOISE_TEXT = {"read more", "subscribe to newsletters", "join us on social", "related", "latest news", "you may also like", "facebook", "twitter", "email", "e-mail", "music news", "feature", "news"}
STOP_TEXT_PATTERNS = [r"^read more$", r"^related$", r"^latest news$", r"^you may also like$", r"^more from$", r"^recommended$"]
NOISE_TEXT_PATTERNS = [
    r"^photo:\s*", r"^photo by\s*", r"^photograph by\s*", r"^image.*courtesy", 
    r"^watch:\s*", r"^read:\s*\[", r"^listen:\s*", r"^exclusive:\s*", # Made 'read:' more specific
    r"^graphic courtesy", r"^all photos courtesy", 
    r"^follow .*", r"^share this.*", r"^advertisement$", 
    r"^sign up.*", r".*newsletter.*", r"^more from.*", 
    r"^related.*", r"^latest news.*"
]
NOISY_CONTAINER_HINTS = ["related", "promo", "card", "teaser", "recommended", "share", "social", "newsletter"]

class GrammyParser:
    """Classe dedicata all'estrazione degli articoli dal dominio Grammy.com."""

    @staticmethod
    def normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    @staticmethod
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
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @staticmethod
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

    @staticmethod
    def is_noise_text(text: str) -> bool:
        t = GrammyParser.normalize_text(text).lower()
        if not t or t in EXACT_NOISE_TEXT:
            return True
        return any(re.search(p, t, re.IGNORECASE) for p in NOISE_TEXT_PATTERNS)

    @staticmethod
    def is_stop_text(text: str) -> bool:
        t = GrammyParser.normalize_text(text).lower()
        return any(re.search(p, t, re.IGNORECASE) for p in STOP_TEXT_PATTERNS)

    @staticmethod
    def looks_like_new_article_title(text: str) -> bool:
        t = GrammyParser.normalize_text(text)
        if len(t) < 20 or len(t) > 160 or t.endswith("."):
            return False
        if "|" in t:
            return True
        promo_patterns = [r"^watch ", r"^listen to ", r"^see the full ", r"^exclusive: "]
        return any(re.search(p, t.lower(), re.IGNORECASE) for p in promo_patterns)

    @staticmethod
    def is_probable_teaser(tag: Tag, text: str) -> bool:
        attrs = GrammyParser.normalize_attrs(tag)
        if any(hint in attrs for hint in NOISY_CONTAINER_HINTS):
            return True
        if len(tag.find_all("a")) >= 3 and len(text) < 180:
            return True
        if tag.name == "p" and len(text) < 120 and GrammyParser.looks_like_new_article_title(text):
            return True
        return False

    @staticmethod
    def remove_global_noise(soup: BeautifulSoup) -> None:
        selectors_da_eliminare = [
            "script", "style", "noscript", "iframe", "svg", "form", "button", 
            "nav", "footer", "aside", "header", 
            ".social-share", ".newsletter", ".related", ".promo-banner", 
            ".ad-container", ".advertisement"
        ]
        for selector in selectors_da_eliminare:
            for tag in soup.select(selector):
                tag.decompose()

    @staticmethod
    def extract_following_blocks_from_title(title_tag: Tag, is_roundup: bool = False) -> list[str]:
        parts, seen_html = [], set()
        started, valid_p_count, bad_streak = False, 0, 0
        title_text = GrammyParser.normalize_text(title_tag.get_text(" ", strip=True))

        for elem in title_tag.next_elements:
            if not isinstance(elem, Tag) or elem is title_tag or elem.name not in {"p", "h2", "h3", "h4", "li"}:
                continue
            text = GrammyParser.normalize_text(elem.get_text(" ", strip=True))
            if not text or text == title_text:
                continue
            if not is_roundup and started and valid_p_count >= 3 and GrammyParser.looks_like_new_article_title(text):
                break
            if GrammyParser.is_stop_text(text):
                break
            if GrammyParser.is_noise_text(text):
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
                if len(text) < (25 if is_roundup else 30) or GrammyParser.is_probable_teaser(elem, text):
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

    @staticmethod
    def extract_grammy_main_content(html: str, url: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        GrammyParser.remove_global_noise(soup)
        title_tag = soup.find("h1")
        if title_tag is None:
            return ""

        title = GrammyParser.normalize_text(title_tag.get_text(" ", strip=True))
        roundup = any(
            h in url.lower() or h in title.lower()
            for h in [
                "new music friday",
                "listen to songs",
                "albums from",
                "songs & albums from",
                "best new songs",
                "best new albums"
            ]
        )

        parts = [f"# {title}"] if title else []
        body_parts = GrammyParser.extract_following_blocks_from_title(title_tag, is_roundup=roundup)

        seen_texts = set()
        for part in body_parts:
            text = GrammyParser.normalize_text(BeautifulSoup(part, "html.parser").get_text(" ", strip=True))
            if text not in seen_texts:
                seen_texts.add(text)
                parts.append(part)

        return GrammyParser.clean_grammy_markdown(
            md("\n".join(parts), heading_style="ATX", strip=["a", "img"])
        ) if parts else ""

    async def parse(self, url: str) -> Dict[str, Any]:
        """Metodo principale che scarica e formatta la pagina di Grammy."""
        try:
            browser_cfg = BrowserConfig(headless=True)
            run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(url=url, config=run_cfg)
                if not result.success or not (html := result.html or "").strip():
                    return {}

                parsed_markdown = self.extract_grammy_main_content(html, url) or ""
                title_tag = BeautifulSoup(html, "html.parser").find("h1")

                return {
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "title": GrammyParser.normalize_text(title_tag.get_text(" ", strip=True)) if title_tag else "GRAMMY Page",
                    "html_text": html,
                    "parsed_text": parsed_markdown,
                }
        except Exception as e:
            logger.error(f"Error parsing Grammy URL {url}: {str(e)}")
            return {}

    async def parse_html(self, url: str, html_text: str) -> Dict[str, Any]:
        """Metodo che esegue il parsing partendo da HTML diretto già fornito in input."""
        try:
            if not html_text or not html_text.strip():
                return {}

            parsed_markdown = self.extract_grammy_main_content(html_text, url) or ""
            title_tag = BeautifulSoup(html_text, "html.parser").find("h1")

            return {
                "url": url,
                "domain": urlparse(url).netloc,
                "title": GrammyParser.normalize_text(title_tag.get_text(" ", strip=True)) if title_tag else "GRAMMY Page",
                "html_text": html_text,
                "parsed_text": parsed_markdown,
            }
        except Exception as e:
            logger.error(f"Error parsing Grammy HTML for URL {url}: {str(e)}")
            return {}