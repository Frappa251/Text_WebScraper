import re
import string
from collections import Counter
from typing import Dict, Any

class TextEvaluator:
    """
    Classe utility per calcolare le metriche di valutazione 
    tra il testo parsato e il Gold Standard.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        """Pulisce il testo per il confronto (rimuove markdown e punteggiatura)."""
        if not text:
            return ""
        text = text.lower()
        # Rimuove i link Markdown [testo](url) tenendo solo 'testo'
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Rimuove simboli Markdown residui
        text = re.sub(r'[\*#_]', '', text)
        # Rimuove punteggiatura e normalizza spazi
        text = text.translate(str.maketrans('', '', string.punctuation))
        return " ".join(text.split())

    @staticmethod
    def calcola_metriche_token(parsed_text: str, gold_text: str) -> Dict[str, float]:
        """Calcola Precision, Recall e F1-Score a livello di token."""
        p_tokens = TextEvaluator.normalize_text(parsed_text).split()
        g_tokens = TextEvaluator.normalize_text(gold_text).split()

        if not g_tokens or not p_tokens:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        p_counts = Counter(p_tokens)
        g_counts = Counter(g_tokens)

        common = sum((p_counts & g_counts).values())
        precision = common / len(p_tokens)
        recall = common / len(g_tokens)
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4)
        }

    @staticmethod
    def calcola_jaccard(parsed_text: str, gold_text: str) -> float:
        """Calcola la Jaccard similarity tra i token normalizzati."""
        p_tokens = set(TextEvaluator.normalize_text(parsed_text).split())
        g_tokens = set(TextEvaluator.normalize_text(gold_text).split())

        union = p_tokens | g_tokens
        intersection = p_tokens & g_tokens

        if not union:
            return 0.0

        return round(len(intersection) / len(union), 4)

    @staticmethod
    def valuta_testo(parsed_text: str, gold_text: str) -> Dict[str, Any]:
        """Restituisce tutte le metriche di valutazione combinate."""
        return {
            "token_level_eval": TextEvaluator.calcola_metriche_token(parsed_text, gold_text),
            "x_eval": {
                "jaccard_similarity": TextEvaluator.calcola_jaccard(parsed_text, gold_text)
            }
        }