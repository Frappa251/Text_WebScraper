from pydantic import BaseModel
from typing import List, Dict, Any

# GET /parse
class ParsedDocument(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str

# GET /domains
class DomainsResponse(BaseModel):
    domains: List[str]

# GET /gold_standard
class GSEntry(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str

# GET /full_gold_standard
class FullGSResponse(BaseModel):
    gold_standard: List[GSEntry]

# POST /evaluate
class EvalInput(BaseModel):
    parsed_text: str
    gold_text: str

class TokenLevelEval(BaseModel):
    precision: float
    recall: float
    f1: float

class EvalResponse(BaseModel):
    token_level_eval: TokenLevelEval
    x_eval: Dict[str, Any] = {}