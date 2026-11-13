import json
from pathlib import Path

from pipeline.lib import wikidata

E = wikidata.ENTITY_PREFIX


def _row(qid: str, fma: str, label: str | None = None) -> dict[str, dict[str, str]]:
    row = {"item": {"type": "uri", "value": E + qid}, "fma": {"type": "literal", "value": fma}}
    if label is not None:
        row["label"] = {"type": "literal", "value": label, "xml:lang": "it"}
    return row


def _parse(tmp_path: Path, rows: list[dict[str, dict[str, str]]]):  # type: ignore[no-untyped-def]
    p = tmp_path / "wd.json"
    p.write_text(json.dumps({"results": {"bindings": rows}}), encoding="utf-8")
    return wikidata.parse_sparql(p)


def test_one_to_one_links_give_a_name(tmp_path: Path) -> None:
    labels, stats = _parse(tmp_path, [_row("Q1", "7197", "fegato")])
    assert labels["FMA:7197"] == wikidata.ItalianLabel("FMA:7197", "fegato", "Q1")
    assert stats.accepted == 1


def test_fma_on_two_items_is_refused(tmp_path: Path) -> None:
    labels, stats = _parse(tmp_path, [_row("Q1", "10", "a"), _row("Q2", "10", "b")])
    assert labels == {}
    assert stats.fma_on_many_items == 1


def test_item_with_two_fma_ids_names_neither(tmp_path: Path) -> None:
    labels, stats = _parse(tmp_path, [_row("Q1", "10", "rene"), _row("Q1", "11", "rene")])
    assert labels == {}
    assert stats.item_with_many_fma == 2


def test_items_without_italian_label_still_count_for_ambiguity(tmp_path: Path) -> None:
    # Q2 non ha nome italiano, ma rende ambiguo FMA:10: Q1 non deve vincere per assenza
    labels, _ = _parse(tmp_path, [_row("Q1", "10", "a"), _row("Q2", "10")])
    assert labels == {}
    labels, _ = _parse(tmp_path, [_row("Q3", "12")])
    assert labels == {}


def test_malformed_rows_are_skipped(tmp_path: Path) -> None:
    labels, _ = _parse(
        tmp_path,
        [_row("Q1", "FMA:10", "x"), {"fma": {"value": "11"}}, _row("Q4", "13", "  ")],
    )
    assert labels == {}
