import asyncio
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def parse_reddit_post(url: str) -> Dict[str, Any]:
    """
    Estrae le informazioni da un post di Reddit combinando Crawl4AI e BeautifulSoup.
    Utilizza le configurazioni avanzate del browser come richiesto dal corso.
    """
    dominio = urlparse(url).netloc

    dati: Dict[str, Any] = {
        "url": url,
        "domain": dominio,
        "title": "",
        "html_text": "",
        "parsed_text": ""
    }

    # 1. Configurazione del browser (headless=True significa invisibile)
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        if not result.success: return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        # 1. Estrazione Titolo precisa
        tag_titolo = soup.find("h1")
        dati["title"] = tag_titolo.get_text(strip=True) if tag_titolo else "Titolo non trovato"

        # 2. Pulizia: Cerchiamo l'area principale del post (shreddit-post)
        # Reddit usa tag specifici come <shreddit-post>. Cerchiamo quello o il div principale.
        main_content = soup.find("shreddit-post") or soup.find("div", {"data-test-id": "post-content"})
        
        if main_content:
            # Rimuoviamo elementi di disturbo interni al post
            for trash in main_content.select("shreddit-post-flair, faceplate-batch, .reward-button"):
                trash.decompose()
            
            # Convertiamo solo l'area del post in Markdown
            dati["parsed_text"] = md(str(main_content), heading_style="ATX")
        else:
            # Fallback se non trova il contenitore specifico
            dati["parsed_text"] = result.markdown # Usa quello di crawl4ai se fallisce soup

        return dati

if __name__ == "__main__":
    url_di_prova = "https://www.reddit.com/r/Universitaly/comments/1s9i7ru/ingegneria_informatica_ragazza_che_copia_a_tutti/"
    risultato_test = asyncio.run(parse_reddit_post(url_di_prova))
    
    for k, v in risultato_test.items():
        valore_stampato = str(v)[:100] + "..." if v and len(str(v)) > 100 else v
        print(f"{k}: {valore_stampato}")