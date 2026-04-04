import re
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


def clean_stackoverflow_markdown(text: str) -> str:
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'^\s*Copy\s*$', '', text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def replace_pre_code_with_fenced_blocks(soup: BeautifulSoup) -> BeautifulSoup:
    for pre in soup.select('pre'):
        code_tag = pre.find('code')
        if not code_tag:
            continue

        language = ''
        for cls in code_tag.get('class', []):
            if cls.startswith('language-'):
                language = cls.split('language-', 1)[1]
                break
            if cls.startswith('lang-'):
                language = cls.split('lang-', 1)[1]
                break

        code_text = code_tag.get_text()
        code_text = code_text.rstrip('\n')
        fence = f'```{language}' if language else '```'
        fenced_block = f'{fence}\n{code_text}\n```'
        pre.replace_with(NavigableString(fenced_block))

    return soup


async def parse_stackoverflow_post(url: str) -> Dict[str, Any]:
    dominio: str = urlparse(url).netloc
    dati: Dict[str, Any] = {
        "url": url,
        "domain": dominio,
        "title": "",
        "html_text": "",
        "parsed_text": ""
    }

    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)

        if not result.success:
            return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        header = soup.find("div", id="question-header")
        if header and header.find("h1"):
            dati["title"] = header.find("h1").get_text(strip=True)
        elif soup.find("h1"):
            dati["title"] = soup.find("h1").get_text(strip=True)

        selectors_da_eliminare = [
            "#sidebar",
            "header",
            "footer",
            ".js-post-menu",
            ".votecell",
            ".comments",
            ".post-signature",
            "#hot-network-questions",
            ".bottom-notice",
            ".js-consent-banner"
        ]

        for selector in selectors_da_eliminare:
            for element in soup.select(selector):
                element.decompose()

        markdown_parts = []

        if dati["title"]:
            markdown_parts.append(f'# {dati["title"]}')

        question_div = soup.select_one("div.question, div#question, div[data-questionid]")
        if question_div:
            q_body = (
                question_div.select_one("div.js-post-body")
                or question_div.select_one("div.s-prose.js-post-body")
                or question_div.select_one("div.s-prose")
                or question_div.select_one("div.post-text")
            )

            if q_body:
                for selector in [
                    ".js-post-notice",
                    ".post-notice",
                    ".community-wiki",
                ]:
                    for el in q_body.select(selector):
                        el.decompose()

                q_body = replace_pre_code_with_fenced_blocks(q_body)
                question_md = md(str(q_body), heading_style="ATX").strip()
                question_md = clean_stackoverflow_markdown(question_md)
                markdown_parts.append(question_md)

        testo_finale = "\n\n".join(markdown_parts)
        testo_finale = re.sub(r'\n{3,}', '\n\n', testo_finale)

        dati["parsed_text"] = testo_finale.strip()
        return dati