from pydantic import BaseModel
from typing import List, Dict, Any

# GET /parse
class ParsedDocument(BaseModel):
    """Modello per la risposta dell'endpoint di parsing."""
    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str

# POST /parse
class ParseHtmlInput(BaseModel):
    """Modello per l'input dell'endpoint di parsing da HTML diretto."""
    url: str
    html_text: str

# GET /domains
class DomainsResponse(BaseModel):
    """Modello per la risposta contenente la lista dei domini supportati."""
    domains: List[str]

# GET /gold_standard
class GSEntry(BaseModel):
    """Modello che rappresenta una singola entry del Gold Standard."""
    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str

# GET /full_gold_standard
class FullGSResponse(BaseModel):
    """Modello per la risposta contenente l'intero Gold Standard di un dominio."""
    gold_standard: List[GSEntry]

# POST /evaluate
class EvalInput(BaseModel):
    """Modello per l'input dell'endpoint di valutazione."""
    parsed_text: str
    gold_text: str

class TokenLevelEval(BaseModel):
    """Modello per le metriche di valutazione a livello di token."""
    precision: float
    recall: float
    f1: float

class EvalResponse(BaseModel):
    """Modello per la risposta finale dell'endpoint di valutazione."""
    token_level_eval: TokenLevelEval
    x_eval: Dict[str, Any] = {}