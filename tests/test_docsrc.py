import io
import tarfile
from pathlib import Path

from pipeline.lib import docsrc

NXML = """<?xml version="1.0" encoding="UTF-8"?>
<book-part-wrapper id="article-99" xmlns:xlink="http://www.w3.org/1999/xlink">
  <book-meta><permissions>
    <license license-type="open-access" xlink:href="{href}"><license-p>x</license-p></license>
  </permissions></book-meta>
  <book-part><book-part-meta><title-group><title>{title}</title></title-group></book-part-meta>
    <body>
      <sec><title>Introduction</title><p>The liver is large.[1] It filters blood.[2,3]</p>
        <sec><title>Detail</title><p>Nested paragraph.[4-6]</p></sec>
      </sec>
      <sec><title>Review Questions</title><p>Skip me.</p></sec>
    </body>
  </book-part>
</book-part-wrapper>"""
NC_ND = "https://creativecommons.org/licenses/by-nc-nd/4.0/"


def chapter(title: str = "Anatomy, Abdomen and Pelvis, Liver", href: str = NC_ND) -> bytes:
    return NXML.format(title=title, href=href).encode()


def test_statpearls_chapter_keeps_license_url_and_clean_text() -> None:
    doc, why = docsrc.parse_statpearls_chapter(chapter())
    assert doc is not None and why == ""
    assert doc.license == "CC BY-NC-ND 4.0"
    assert doc.url == "https://www.ncbi.nlm.nih.gov/books/n/statpearls/article-99/"
    assert doc.refs == [("anatomy", "Liver")]
    assert "The liver is large. It filters blood." in doc.text  # niente [1], [2,3]
    assert "Nested paragraph." in doc.text and "[4-6]" not in doc.text
    assert "Skip me" not in doc.text


def test_unknown_license_or_archived_chapters_are_refused() -> None:
    assert docsrc.parse_statpearls_chapter(chapter(href="https://example.org/x"))[1].startswith(
        "license"
    )
    assert docsrc.parse_statpearls_chapter(chapter(title="Old Topic (Archived)")) == (None, "other")


def test_read_statpearls_streams_the_archive(tmp_path: Path) -> None:
    path = tmp_path / "sp.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, data in [
            ("sp/article-1.nxml", chapter()),
            ("sp/nurse-article-1.nxml", chapter()),
            ("sp/article-2.nxml", chapter(href="https://example.org/x")),
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    stats = docsrc.ReadStats()
    docs = list(docsrc.read_statpearls(path, stats))
    assert len(docs) == 1 and stats.skipped_license == 1


def test_anatomy_subject() -> None:
    assert (
        docsrc.anatomy_subject("Anatomy, Head and Neck, Cricoid Cartilage") == "Cricoid Cartilage"
    )
    assert docsrc.anatomy_subject("Anatomy, Bony Pelvis and Lower Limb: Calcaneus") == "Calcaneus"
    assert docsrc.anatomy_subject("Anatomy and Physiology") is None
    assert docsrc.anatomy_subject("Hepatitis B") is None


def test_medlineplus_and_orphanet(tmp_path: Path) -> None:
    mp = tmp_path / "mp.xml"
    mp.write_text(
        '<health-topics><health-topic title="Liver Diseases" url="https://medlineplus.gov/l.html"'
        ' id="7" language="English"><also-called>Hepatic disease</also-called>'
        "<full-summary>&lt;p&gt;Your liver &lt;b&gt;works&lt;/b&gt;.&lt;/p&gt;</full-summary>"
        '<mesh-heading><descriptor id="D008107">Liver Diseases</descriptor></mesh-heading>'
        '</health-topic><health-topic title="Hígado" id="8" language="Spanish">'
        "<full-summary>x</full-summary></health-topic></health-topics>",
        encoding="utf-8",
    )
    [doc] = docsrc.read_medlineplus(mp)
    assert doc.doc_id == "medlineplus:7" and doc.refs == [("MESH", "D008107")]
    assert doc.text == "Liver Diseases (also called: Hepatic disease)\n\nYour liver works."

    op = tmp_path / "op.xml"
    op.write_text(
        "<JDBOR><Availability><Licence><ShortIdentifier>CC-BY-4.0</ShortIdentifier></Licence>"
        "</Availability><DisorderList><Disorder><OrphaCode>141</OrphaCode>"
        '<Name lang="en">Canavan disease</Name><SynonymList/><ExternalReferenceList>'
        "<ExternalReference><Source>MONDO</Source><Reference>0010079</Reference>"
        '<DisorderMappingRelation><Name lang="en">E (Exact mapping)</Name>'
        "</DisorderMappingRelation></ExternalReference>"
        "<ExternalReference><Source>MONDO</Source><Reference>0000001</Reference>"
        '<DisorderMappingRelation><Name lang="en">NTBT (narrower)</Name>'
        "</DisorderMappingRelation></ExternalReference></ExternalReferenceList>"
        '<SummaryInformationList><SummaryInformation lang="en"><TextSectionList>'
        '<TextSection lang="en"><TextSectionType><Name lang="en">Definition</Name>'
        "</TextSectionType><Contents>A leukodystrophy.</Contents></TextSection>"
        "</TextSectionList></SummaryInformation></SummaryInformationList></Disorder>"
        "</DisorderList></JDBOR>",
        encoding="utf-8",
    )
    [doc] = docsrc.read_orphanet(op)
    assert doc.license == "CC BY 4.0"
    assert doc.refs == [("Orphanet", "141"), ("MONDO", "MONDO:0010079")]  # solo il mapping E
    assert doc.text.endswith("Definition: A leukodystrophy.")
