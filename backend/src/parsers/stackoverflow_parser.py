import asyncio
import re
from urllib.parse import urlparse
from typing import Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def parse_stackoverflow_post(url: str) -> Dict[str, Any]:
    """
    Estrae la domanda e le risposte da un thread di StackOverflow.
    
    Per massimizzare la Precision dell'Evaluator, questo parser filtra
    attivamente sidebar, commenti, metadati utente (reputazione, badge),
    bottoni di voto e sezioni "Related Questions".
    
    Args:
        url (str): L'URL del thread di StackOverflow.
        
    Returns:
        Dict[str, Any]: Dizionario contenente url, domain, title, html_text e parsed_text.
    """
    dominio: str = urlparse(url).netloc
    dati: Dict[str, Any] = {
        "url": url,
        "domain": dominio,
        "title": "",
        "html_text": "",
        "parsed_text": ""
    }

    # 1. Configurazione invisibile del browser (bypass cache per dati freschi)
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        
        if not result.success:
            return dati

        dati["html_text"] = result.html
        soup = BeautifulSoup(result.html, "html.parser")

        # 2. Estrazione del Titolo
        header = soup.find("div", id="question-header")
        if header and header.find("h1"):
            dati["title"] = header.find("h1").get_text(strip=True)

        # 3. Pulizia Aggressiva (Rimozione del "Rumore")
        # Rimuoviamo tutto ciò che non è Domanda o Risposta pura
        selectors_da_eliminare = [
            "#sidebar",                 # Sidebar destra
            "header",                   # Top bar del sito
            "footer",                   # Piè di pagina
            ".js-post-menu",            # Bottoni Share, Edit, Follow
            ".votecell",                # Colonna dei voti (freccette su/giù)
            ".comments",                # Commenti sotto ai post (spesso irrilevanti)
            ".post-signature",          # Box autore (nome utente, badge, avatar)
            "#hot-network-questions",   # Sezione link esterni
            ".bottom-notice",           # Avvisi a fondo pagina
            ".js-consent-banner"        # Banner dei cookie
        ]
        
        for selector in selectors_da_eliminare:
            for element in soup.select(selector):
                element.decompose()

        # 4. Estrazione del Contenuto (Domanda + Risposte)
        markdown_parts = []
        
        # Aggiungiamo il titolo come H1 nel Markdown
        if dati["title"]:
            markdown_parts.append(f"# {dati['title']}")

        # --- A. Estrazione della Domanda ---
        question_div = soup.find("div", class_="question")
        if question_div:
            # .s-prose è la classe di StackOverflow per i blocchi di testo e codice
            q_body = question_div.find("div", class_="s-prose")
            if q_body:
                markdown_parts.append(md(str(q_body), heading_style="ATX").strip())

        # --- B. Estrazione delle Risposte ---
        answers_container = soup.find("div", id="answers")
        if answers_container:
            # Troviamo tutti i div che contengono una singola risposta
            answers = answers_container.find_all("div", class_="answer")
            for i, answer in enumerate(answers, 1):
                a_body = answer.find("div", class_="s-prose")
                if a_body:
                    # Aggiungiamo un sottotitolo H2 per ogni risposta per mantenere ordine
                    markdown_parts.append(f"## Answer {i}")
                    markdown_parts.append(md(str(a_body), heading_style="ATX").strip())

        # 5. Assemblaggio Finale
        # Uniamo tutto con doppio a capo per simulare una formattazione perfetta
        testo_finale = "\n\n".join(markdown_parts)

        # Opzionale: Riduciamo a massimo 2 a capo consecutivi nel caso ci siano buchi enormi
        testo_finale = re.sub(r'\n{3,}', '\n\n', testo_finale)

        dati["parsed_text"] = testo_finale.strip()

        return dati

# --- Blocco di Test Locale ---
if __name__ == "__main__":
    test_url = "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-processing-an-unsorted-array"
    risultato = asyncio.run(parse_stackoverflow_post(test_url))
    
    print(f"TITOLO: {risultato['title']}\n")
    print("--- TESTO PARSATO ---")
    print(risultato["parsed_text"][:500] + "\n...[TRUNCATED]")