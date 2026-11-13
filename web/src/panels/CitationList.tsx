import type { Citation } from "../api/client";

const SOURCE_NAMES: Record<string, string> = {
  bodyparts3d: "BodyParts3D",
  fma: "Foundational Model of Anatomy",
  uberon: "Uberon",
  hpo: "Human Phenotype Ontology",
  hpoa: "HPO Annotations",
  mondo: "Mondo Disease Ontology",
  doid: "Human Disease Ontology",
  icd11: "ICD-11 MMS",
  wikidata: "Wikidata",
  statpearls: "StatPearls",
  medlineplus: "MedlinePlus",
  orphanet: "Orphanet",
};

export const sourceName = (source: string): string => SOURCE_NAMES[source] ?? source;

/** 'uberon/releases/2026-11-05/uberon-basic.owl' → '2026-11-05' (solo per la lettura). */
export function shortVersion(version: string): string {
  return /\d{4}-\d{2}-\d{2}/.exec(version)?.[0] ?? version;
}

/**
 * Le fonti da cui proviene ciò che la scheda afferma, una riga per fonte.
 * Il rimando puntuale sta accanto a ogni voce (l'identificatore è il link al
 * documento); qui si dichiarano versione e licenza.
 */
export function CitationList({ citations }: { citations: Citation[] }) {
  const bySource = new Map<string, Citation>();
  for (const c of citations) if (!bySource.has(c.source)) bySource.set(c.source, c);
  if (bySource.size === 0) return null;

  return (
    <section aria-labelledby="fonti" className="mt-8 border-t border-gauze-300 pt-4">
      <h3 id="fonti" className="text-[0.82rem] font-semibold text-ink-soft">
        Fonti di questa scheda
      </h3>
      <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-[0.8rem] text-ink-mute">
        {[...bySource.values()].map((c) => (
          <div key={c.source} className="contents">
            <dt>
              {sourceName(c.source)}
              <span className="tnum"> {shortVersion(c.version)}</span>
            </dt>
            <dd className="text-right">{c.license}</dd>
          </div>
        ))}
      </dl>
      <a
        href="/attribution"
        className="mt-3 inline-block text-[0.8rem] text-iodine-700 underline decoration-iodine-600/40 underline-offset-2 hover:decoration-iodine-700"
      >
        Tutte le fonti e le attribuzioni
      </a>
    </section>
  );
}
