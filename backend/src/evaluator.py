import re
import string
from collections import Counter

def normalize_text(text: str) -> str:
    """Pulisce il testo per il confronto (indispensabile per la Precision)."""
    if not text: return ""
    text = text.lower()
    # Rimuove i link Markdown [testo](url) tenendo solo 'testo'
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Rimuove simboli Markdown residui
    text = re.sub(r'[\*#_]', '', text)
    # Rimuove punteggiatura e normalizza spazi
    text = text.translate(str.maketrans('', '', string.punctuation))
    return " ".join(text.split())

def calcola_metriche_token(parsed_text: str, gold_text: str) -> dict:
    p_tokens = normalize_text(parsed_text).split()
    g_tokens = normalize_text(gold_text).split()
    
    if not g_tokens: return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    if not p_tokens: return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Conta le occorrenze delle parole (più preciso del semplice 'set')
    p_counts = Counter(p_tokens)
    g_counts = Counter(g_tokens)
    
    # Calcola l'intersezione pesata (quante parole del parser sono davvero nel Gold)
    common = sum((p_counts & g_counts).values())
    
    precision = common / len(p_tokens)
    recall = common / len(g_tokens)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }