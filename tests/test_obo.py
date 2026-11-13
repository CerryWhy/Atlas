from pathlib import Path

from pipeline.lib import obo

SAMPLE = r"""format-version: 1.2
data-version: releases/2099-01-01
property_value: terms:license http://creativecommons.org/licenses/by/4.0/

[Term]
id: MONDO:0000001
name: example disease
def: "A \"quoted\" definition." [PMID:1]
xref: icd11.foundation:123 {source="MONDO:equivalentTo"}
relationship: disease_has_location UBERON:0002107 ! liver

[Term]
id: MONDO:0000002
name: gone
is_obsolete: true

[Typedef]
id: disease_has_location
"""


def test_parse_terms(tmp_path: Path) -> None:
    p = tmp_path / "x.obo"
    p.write_text(SAMPLE, encoding="utf-8")
    terms = obo.load_terms(p)
    t = terms["MONDO:0000001"]
    assert t.name == "example disease"
    assert t.definition == 'A "quoted" definition.'
    assert t.xrefs == ["icd11.foundation:123"]
    assert t.relations == [("disease_has_location", "UBERON:0002107")]
    assert terms["MONDO:0000002"].obsolete
    assert "disease_has_location" not in terms
    assert obo.data_version(p) == "releases/2099-01-01"
    assert obo.license_url(p) == "http://creativecommons.org/licenses/by/4.0/"
