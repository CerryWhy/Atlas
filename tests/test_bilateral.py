import importlib

from pipeline.lib.obo import Term

load = importlib.import_module("pipeline.03_load_ontologies")


def test_bilateral_by_name_or_by_declared_modifier() -> None:
    terms = [
        Term(id="HP:9000001", name="Bilateral"),  # il modificatore, trovato per nome
        Term(id="HP:9000002", name="Bilateral renal agenesis"),
        Term(id="HP:9000003", name="Renal hypoplasia, bilaterally"),
        Term(
            id="HP:9000004",
            name="Absent kidneys",
            relations=[("has_modifier", "HP:9000001")],
        ),
        Term(id="HP:9000005", name="Unilateral renal agenesis"),
        Term(id="HP:9000006", name="Multilateral thing"),  # "bilateral" non è una parola qui
    ]
    found = load.bilateral_ids(terms)
    assert {"HP:9000002", "HP:9000003", "HP:9000004"} <= found
    assert not {"HP:9000005", "HP:9000006"} & found
