import type { Citation } from "../api/client";

/** Elenco numerato delle fonti. Ogni voce è un documento apribile (I2). */
export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <ol className="space-y-1 text-xs text-zinc-400">
      {citations.map((c, i) => (
        <li key={`${c.url}|${c.title}`} id={`cite-${i + 1}`} className="flex gap-2">
          <span className="font-mono text-zinc-500">[{i + 1}]</span>
          <span>
            <a href={c.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
              {c.title}
            </a>{" "}
            <span className="text-zinc-500">
              · {c.version} · {c.license}
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Deduplica le citazioni e restituisce l'indice (1-based) di ciascuna. */
export function indexCitations(groups: Citation[][]): {
  list: Citation[];
  refs: number[][];
} {
  const list: Citation[] = [];
  const key = (c: Citation) => `${c.url}|${c.title}`;
  const seen = new Map<string, number>();
  const refs = groups.map((g) =>
    g.map((c) => {
      const k = key(c);
      let n = seen.get(k);
      if (n === undefined) {
        list.push(c);
        n = list.length;
        seen.set(k, n);
      }
      return n;
    }),
  );
  return { list, refs };
}
