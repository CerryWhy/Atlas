"""Divisione dei documenti in chunk per la ricerca vettoriale.

Un chunk è una sequenza di paragrafi interi fino a `size` caratteri; un paragrafo più
lungo si divide tra frasi. Nessuna sovrapposizione: la citazione di un chunk rimanda
al documento intero, che resta apribile alla fonte.
"""

import re

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")


def _split_long(paragraph: str, size: int) -> list[str]:
    out: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > size:  # una "frase" enorme (tabella appiattita): taglio netto
            if current:
                out.append(current)
                current = ""
            out.append(sentence[:size])
            sentence = sentence[size:]
        if current and len(current) + 1 + len(sentence) > size:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


def chunk_text(text: str, size: int) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    pieces: list[str] = []
    for p in paragraphs:
        pieces += _split_long(p, size) if len(p) > size else [p]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 2 + len(piece) > size:
            chunks.append(current)
            current = piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks
