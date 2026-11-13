"""Lettori del corpus testuale (Fase 3): MedlinePlus, Orphanet, StatPearls.

Ogni lettore restituisce `Doc`: testo pulito, URL apribile, licenza e i riferimenti
che la FONTE dichiara (codici MeSH, ORPHAcode, MONDO; per StatPearls il titolo dei
capitoli di anatomia). Il collegamento a malattie e strutture lo fa 06, solo a partire
da questi riferimenti (I5).

Licenze (I3): ogni documento porta una licenza accertata. Quando il file la dichiara
(Orphanet, StatPearls) si legge dal file, documento per documento; quando la dichiara
il sito (MedlinePlus) la si riporta da lì con il riferimento. Un documento la cui
licenza non è tra quelle riconosciute qui viene scartato e contato, mai caricato.
"""

import html
import re
import tarfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

# Licenze riconosciute: URL o identificatore dichiarato → nome mostrato in app.
LICENSE_NAMES = {
    "https://creativecommons.org/licenses/by-nc-nd/4.0/": "CC BY-NC-ND 4.0",
    "http://creativecommons.org/licenses/by-nc-nd/4.0/": "CC BY-NC-ND 4.0",
    "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "http://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "CC-BY-4.0": "CC BY 4.0",
}
# MedlinePlus: "Summaries on health topic pages" sono nel pubblico dominio,
# https://medlineplus.gov/about/using/usingcontent/
MEDLINEPLUS_LICENSE = "Public domain (U.S. government work)"


@dataclass
class Doc:
    doc_id: str  # 'medlineplus:6308' | 'orphanet:166024' | 'statpearls:article-20545'
    source: str
    title: str
    url: str
    license: str
    text: str
    # riferimenti dichiarati dalla fonte: ('MESH', 'D006442'), ('Orphanet', '166024'),
    # ('MONDO', 'MONDO:0011778'), ('anatomy', 'Liver')
    refs: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ReadStats:
    read: int = 0
    skipped_license: int = 0
    skipped_empty: int = 0
    skipped_other: int = 0
    licenses_seen: dict[str, int] = field(default_factory=dict)

    def count_license(self, name: str) -> None:
        self.licenses_seen[name] = self.licenses_seen.get(name, 0) + 1


# ─── testo ──────────────────────────────────────────────────────────────────
_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(p|li|ul|ol|h[1-6]|br|div|tr)\b[^>]*>", re.IGNORECASE)
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BLANKS = re.compile(r"\n\s*\n+")
# Rimandi alla bibliografia del capitolo ("[1]", "[2][3]", "[4,5]", "[6-8]"): la
# bibliografia non si carica, e nella Fase 4 si confonderebbero con i marcatori [n]
# delle citazioni dell'assistente.
_REF_MARKS = re.compile(r"\s?\[\d+(?:\s*[,\u2013-]\s*\d+)*\]")


def html_to_text(markup: str) -> str:
    """HTML (già unescaped dal parser XML) → testo a paragrafi."""
    text = _BLOCK.sub("\n\n", markup)
    text = html.unescape(_TAG.sub("", text))
    text = _SPACES.sub(" ", text)
    return _BLANKS.sub("\n\n", "\n".join(line.strip() for line in text.split("\n"))).strip()


def _itertext(elem: ET.Element) -> str:
    return _SPACES.sub(" ", "".join(elem.itertext())).strip()


# ─── MedlinePlus ────────────────────────────────────────────────────────────
def read_medlineplus(path: Path, stats: ReadStats | None = None) -> Iterator[Doc]:
    """Health topics in inglese da mplus_topics_<data>.xml."""
    stats = stats if stats is not None else ReadStats()
    for _event, el in ET.iterparse(path, events=("end",)):
        if el.tag != "health-topic":
            continue
        if el.get("language") != "English":
            el.clear()
            continue
        summary = el.findtext("full-summary") or ""
        text = html_to_text(summary)
        title = (el.get("title") or "").strip()
        if not text or not title:
            stats.skipped_empty += 1
            el.clear()
            continue
        also = [a.text.strip() for a in el.findall("also-called") if a.text]
        refs = [
            ("MESH", d.get("id", ""))
            for d in el.findall("mesh-heading/descriptor")
            if d.get("id", "").startswith("D")
        ]
        head = title + (f" (also called: {', '.join(also)})" if also else "")
        stats.read += 1
        stats.count_license(MEDLINEPLUS_LICENSE)
        yield Doc(
            doc_id=f"medlineplus:{el.get('id')}",
            source="medlineplus",
            title=title,
            url=el.get("url") or "https://medlineplus.gov/",
            license=MEDLINEPLUS_LICENSE,
            text=f"{head}\n\n{text}",
            refs=refs,
        )
        el.clear()


# ─── Orphanet ───────────────────────────────────────────────────────────────
def orphanet_license(path: Path) -> str | None:
    """La licenza dichiarata nell'intestazione del file Orphadata."""
    for _event, el in ET.iterparse(path, events=("end",)):
        if el.tag == "ShortIdentifier":
            return LICENSE_NAMES.get((el.text or "").strip())
        if el.tag == "Disorder":  # oltre l'intestazione: non c'è
            return None
    return None


_ORPHA_SECTIONS = "SummaryInformationList/SummaryInformation/TextSectionList/TextSection"


def read_orphanet(path: Path, stats: ReadStats | None = None) -> Iterator[Doc]:
    """Definizioni dei disordini da en_product1.xml, con i legami MONDO esatti (E)."""
    stats = stats if stats is not None else ReadStats()
    lic = orphanet_license(path)
    for _event, el in ET.iterparse(path, events=("end",)):
        if el.tag != "Disorder":
            continue
        code = (el.findtext("OrphaCode") or "").strip()
        name = (el.findtext("Name") or "").strip()
        sections = [
            (
                (s.findtext("TextSectionType/Name") or "").strip(),
                html_to_text(s.findtext("Contents") or ""),
            )
            for s in el.findall(_ORPHA_SECTIONS)
            if s.get("lang", "en") == "en"
        ]
        sections = [(t, c) for t, c in sections if c]
        if not code or not name or not sections:
            stats.skipped_empty += 1
            el.clear()
            continue
        if lic is None:
            stats.skipped_license += 1
            el.clear()
            continue
        synonyms = [s.text.strip() for s in el.findall("SynonymList/Synonym") if s.text]
        refs: list[tuple[str, str]] = [("Orphanet", code)]
        for ref in el.findall("ExternalReferenceList/ExternalReference"):
            relation = ref.findtext("DisorderMappingRelation/Name") or ""
            if ref.findtext("Source") == "MONDO" and relation.startswith("E "):
                number = (ref.findtext("Reference") or "").strip()
                if number.isdigit():
                    refs.append(("MONDO", f"MONDO:{number.zfill(7)}"))
        head = name + (f" (synonyms: {', '.join(synonyms)})" if synonyms else "")
        body = "\n\n".join(f"{t}: {c}" if t else c for t, c in sections)
        stats.read += 1
        stats.count_license(lic)
        yield Doc(
            doc_id=f"orphanet:{code}",
            source="orphanet",
            title=name,
            url=f"https://www.orpha.net/en/disease/detail/{code}",
            license=lic,
            text=f"{head}\n\n{body}",
            refs=refs,
        )
        el.clear()


# ─── StatPearls (NCBI Bookshelf, FTP litarch) ───────────────────────────────
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
# Sezioni che non sono contenuto clinico citabile.
_SKIP_SECTIONS = {
    "review questions",
    "references",
    "continuing education activity",
    "disclosure",
}
# "Anatomy, Abdomen and Pelvis, Liver" | "Anatomy, Bony Pelvis and Lower Limb: Calcaneus"
_ANATOMY_TITLE = re.compile(r"^Anatomy,\s.+?[,:]\s*([^,:]+?)\s*$")


def anatomy_subject(title: str) -> str | None:
    """L'oggetto di un capitolo della serie di anatomia: l'ultimo segmento del titolo."""
    m = _ANATOMY_TITLE.match(title.strip())
    return m.group(1).strip() if m else None


def _sections(body: ET.Element) -> Iterator[tuple[str, str]]:
    for sec in body.iter("sec"):
        title_el = sec.find("title")
        title = _itertext(title_el) if title_el is not None else ""
        if title.lower() in _SKIP_SECTIONS:
            continue
        paras = [_REF_MARKS.sub("", _itertext(p)) for p in sec.findall("p")]
        text = "\n\n".join(p for p in paras if p)
        if text:
            yield title, text


def parse_statpearls_chapter(data: bytes) -> tuple[Doc | None, str]:
    """(documento, motivo dello scarto). Un capitolo = un file BITS .nxml."""
    root = ET.fromstring(data)
    part_id = root.get("id") or ""
    lic_el = root.find(".//book-meta/permissions/license")
    href = lic_el.get(XLINK_HREF, "") if lic_el is not None else ""
    lic = LICENSE_NAMES.get(href)
    title_el = root.find(".//book-part-meta/title-group/title")
    title = _itertext(title_el) if title_el is not None else ""
    body = root.find(".//book-part/body")
    if not part_id or not title or body is None:
        return None, "empty"
    if "(archived)" in title.lower():
        return None, "other"  # capitolo ritirato dall'editore: non è più contenuto corrente
    if lic is None:
        return None, f"license:{href or '—'}"
    text = "\n\n".join(f"{t}\n{c}" if t else c for t, c in _sections(body))
    if not text:
        return None, "empty"
    refs = [("anatomy", s)] if (s := anatomy_subject(title)) else []
    return (
        Doc(
            doc_id=f"statpearls:{part_id}",
            source="statpearls",
            title=title,
            url=f"https://www.ncbi.nlm.nih.gov/books/n/statpearls/{part_id}/",
            license=lic,
            text=f"{title}\n\n{text}",
            refs=refs,
        ),
        "",
    )


def read_statpearls(path: Path, stats: ReadStats | None = None) -> Iterator[Doc]:
    """Capitoli dall'archivio litarch (tar.gz), letti in streaming senza estrarre.
    Le versioni "nurse-article" ripetono i capitoli per l'infermieristica: si saltano."""
    stats = stats if stats is not None else ReadStats()
    with tarfile.open(path, mode="r|gz") as tar:
        for member in tar:
            name = Path(member.name).name
            if not member.isfile() or not name.startswith("article-") or not name.endswith(".nxml"):
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            doc, why = parse_statpearls_chapter(fh.read())
            if doc is None:
                if why.startswith("license"):
                    stats.skipped_license += 1
                    stats.count_license(why)
                elif why == "empty":
                    stats.skipped_empty += 1
                else:
                    stats.skipped_other += 1
                continue
            stats.read += 1
            stats.count_license(doc.license)
            yield doc
