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
        """
        Pulisce e standardizza una stringa di testo per prepararla al confronto metrico: 
        converte in minuscolo, rimuove link markdown, simboli spuri e punteggiatura.

        Args:
            text (str): Il testo grezzo da normalizzare.

        Returns:
            str: Il testo pulito e privo di punteggiatura.
        """
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'[\*#_]', '', text)
        text = text.translate(str.maketrans('', '', string.punctuation))
        return " ".join(text.split())

    @staticmethod
    def calcola_metriche_token(parsed_text: str, gold_text: str) -> Dict[str, float]:
        """
        Calcola le metriche di classificazione (Precision, Recall, F1-Score) confrontando 
        le frequenze dei token (parole) tra il testo estratto e il Gold Standard.

        Args:
            parsed_text (str): Il testo prodotto dal sistema di parsing.
            gold_text (str): Il testo di riferimento perfetto (Gold Standard).

        Returns:
            Dict[str, float]: Dizionario contenente i valori di precision, recall e f1 arrotondati.
        """
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
        """
        Calcola l'indice di somiglianza di Jaccard (intersezione su unione) tra gli insiemi 
        unici di parole del testo parsato e del Gold Standard.

        Args:
            parsed_text (str): Il testo prodotto dal sistema di parsing.
            gold_text (str): Il testo di riferimento (Gold Standard).

        Returns:
            float: Il coefficiente di similarità di Jaccard arrotondato a 4 decimali.
        """
        p_tokens = set(TextEvaluator.normalize_text(parsed_text).split())
        g_tokens = set(TextEvaluator.normalize_text(gold_text).split())

        union = p_tokens | g_tokens
        intersection = p_tokens & g_tokens

        if not union:
            return 0.0

        return round(len(intersection) / len(union), 4)

    @staticmethod
    def valuta_testo(parsed_text: str, gold_text: str) -> Dict[str, Any]:
        """
        Metodo orchestratore che aggrega tutte le metriche di valutazione (token-level e custom) 
        in un'unica struttura dati.

        Args:
            parsed_text (str): Il testo estratto dal parser.
            gold_text (str): Il testo di riferimento.

        Returns:
            Dict[str, Any]: Dizionario strutturato contenente 'token_level_eval' e metriche 'x_eval'.
        """
        return {
            "token_level_eval": TextEvaluator.calcola_metriche_token(parsed_text, gold_text),
            "x_eval": {
                "jaccard_similarity": TextEvaluator.calcola_jaccard(parsed_text, gold_text)
            }
        }