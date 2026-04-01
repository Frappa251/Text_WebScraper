import asyncio
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def parse_reddit_post(url: str) -> Dict[str, Any]:
    """
    Estrae le informazioni da un post di Reddit combinando Crawl4AI e BeautifulSoup.
    Utilizza le configurazioni avanzate del browser come richiesto dal corso.
    """
    dominio = urlparse(url).netloc

    dati_estratti: Dict[str, Any] = {
        "url": url,
        "domain": dominio,
        "title": "",
        "html_text": "",
        "parsed_text": ""
    }

    # 1. Configurazione del browser (headless=True significa invisibile)
    browser_cfg = BrowserConfig(headless=True)
    
    # 2. Configurazione del run (scarica sempre dalla rete, ignora la cache)
    crawler_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    # 3. Avvio del crawler passando le configurazioni come nella slide
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        risultato = await crawler.arun(url=url, config=crawler_cfg)
        
        if not risultato.success:
            return dati_estratti
        
        dati_estratti["html_text"] = risultato.html
        dati_estratti["parsed_text"] = risultato.markdown
        
        # Estrazione del titolo tramite BeautifulSoup
        zuppa = BeautifulSoup(risultato.html, "html.parser")
        tag_titolo = zuppa.find("title")
        
        if tag_titolo and tag_titolo.text:
            dati_estratti["title"] = tag_titolo.text.strip()
            
        return dati_estratti

if __name__ == "__main__":
    url_di_prova = "https://www.reddit.com/r/Python/comments/1example/test_post/"
    risultato_test = asyncio.run(parse_reddit_post(url_di_prova))
    
    for k, v in risultato_test.items():
        valore_stampato = str(v)[:100] + "..." if v and len(str(v)) > 100 else v
        print(f"{k}: {valore_stampato}")