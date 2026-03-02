from __future__ import annotations

from collections import Counter, defaultdict


def tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in text.split() if tok.isalpha()]


def train(samples: list[tuple[str, str]]) -> tuple[dict[str, Counter[str]], Counter[str]]:
    word_counts: dict[str, Counter[str]] = defaultdict(Counter)
    label_counts: Counter[str] = Counter()
    for label, text in samples:
        label_counts[label] += 1
        for token in tokenize(text):
            word_counts[label][token] += 1
    return dict(word_counts), label_counts


def predict(model: tuple[dict[str, Counter[str]], Counter[str]], text: str) -> str:
    word_counts, label_counts = model
    tokens = tokenize(text)
    best_label = ''
    best_score = float('-inf')
    for label, prior in label_counts.items():
        score = float(prior)
        vocab_total = sum(word_counts[label].values()) + 1
        for token in tokens:
            score += word_counts[label][token] / vocab_total
        if score > best_score:
            best_label, best_score = label, score
    return best_label


def run_demo() -> dict[str, object]:
    model = train([('spam', 'buy now offer'), ('ham', 'meeting schedule update')])
    result = predict(model, 'buy offer now')
    return {'project': 'nlp_text_classifier', 'prediction': result}


if __name__ == '__main__':
    print(run_demo())
