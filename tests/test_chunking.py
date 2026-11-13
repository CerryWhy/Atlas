from pipeline.lib import chunking


def test_paragraphs_are_packed_without_being_cut() -> None:
    text = "\n\n".join(["a" * 400, "b" * 400, "c" * 400, "d" * 400])
    chunks = chunking.chunk_text(text, 1000)
    assert chunks == ["a" * 400 + "\n\n" + "b" * 400, "c" * 400 + "\n\n" + "d" * 400]


def test_long_paragraphs_split_between_sentences() -> None:
    sentences = [f"Sentence {i} " + "x" * 80 + "." for i in range(30)]
    chunks = chunking.chunk_text(" ".join(sentences), 500)
    assert all(len(c) <= 500 for c in chunks)
    assert all(c.endswith(".") for c in chunks)  # mai a metà frase
    assert " ".join(chunks) == " ".join(sentences)


def test_nothing_is_lost_even_for_huge_sentences() -> None:
    blob = "y" * 2500
    chunks = chunking.chunk_text(f"Intro.\n\n{blob}", 1000)
    assert "".join(c for c in chunks if c != "Intro.") == blob
    assert all(len(c) <= 1000 for c in chunks)
