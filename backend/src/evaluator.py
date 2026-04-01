def tokenize(text: str) -> set:
    return set(text.lower().split())


def calcola_metriche_token(parsed_text: str, gold_text: str) -> dict:
    tokens_pred = tokenize(parsed_text)
    tokens_gold = tokenize(gold_text)

    intersection = tokens_pred & tokens_gold

    precision = len(intersection) / len(tokens_pred) if tokens_pred else 0
    recall = len(intersection) / len(tokens_gold) if tokens_gold else 0

    if precision + recall == 0:
        f1 = 0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }