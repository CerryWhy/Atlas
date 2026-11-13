import { useEffect, useState } from "react";
import { getStructure, type Structure } from "../api/client";
import { useAtlasStore } from "../store/atlas";
import { CitationList, indexCitations } from "./CitationList";

type Load =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ok"; data: Structure };

function Refs({ ns }: { ns: number[] }) {
  return (
    <sup className="ml-1 font-mono text-[10px] text-sky-400">
      {ns.map((n) => (
        <a key={n} href={`#cite-${n}`} className="hover:underline">
          [{n}]
        </a>
      ))}
    </sup>
  );
}

/** Cosa hai selezionato: identità della struttura e patologie con sede lì. */
export function StructurePanel() {
  const selected = useAtlasStore((s) => s.selected);
  const [load, setLoad] = useState<Load>({ state: "idle" });

  useEffect(() => {
    if (!selected) {
      setLoad({ state: "idle" });
      return;
    }
    const ctrl = new AbortController();
    setLoad({ state: "loading" });
    getStructure(selected, ctrl.signal)
      .then((data) => setLoad({ state: "ok", data }))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoad({ state: "error", message: String(e) });
      });
    return () => ctrl.abort();
  }, [selected]);

  if (load.state === "idle")
    return <p className="text-sm text-zinc-400">Clicca una struttura per esplorarla.</p>;
  if (load.state === "loading") return <p className="text-sm text-zinc-400">Caricamento…</p>;
  if (load.state === "error") return <p className="text-sm text-red-400">{load.message}</p>;

  const s = load.data;
  const { list, refs } = indexCitations([s.citations, ...s.diseases.map((d) => d.citations)]);
  const [structureRefs = [], ...diseaseRefs] = refs;

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-xl font-semibold capitalize text-zinc-100">
          {s.label_it ?? s.label_en}
          <Refs ns={structureRefs} />
        </h2>
        {s.label_la && <p className="italic text-zinc-400">{s.label_la}</p>}
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 font-mono text-xs text-zinc-400">
          <dt>FMA</dt>
          <dd>{s.fma_id}</dd>
          {s.uberon_id && (
            <>
              <dt>UBERON</dt>
              <dd>{s.uberon_id}</dd>
            </>
          )}
          {s.system && (
            <>
              <dt>Sistema</dt>
              <dd>{s.system}</dd>
            </>
          )}
        </dl>
      </header>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Patologie con sede in questa struttura
        </h3>
        {s.diseases.length === 0 ? (
          <p className="text-sm text-zinc-500">Nessuna patologia collegata in atlas.db.</p>
        ) : (
          <ul className="space-y-2">
            {s.diseases.map((d, i) => (
              <li key={d.mondo_id} className="rounded-md bg-zinc-800/60 px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm text-zinc-100">
                    {d.label}
                    <Refs ns={diseaseRefs[i] ?? []} />
                  </span>
                  {d.icd11_code && (
                    <span
                      className="shrink-0 rounded bg-amber-900/50 px-1.5 py-0.5 font-mono text-xs text-amber-200"
                      title="Codice ICD-11 MMS"
                    >
                      {d.icd11_code}
                    </span>
                  )}
                </div>
                <div className="font-mono text-[11px] text-zinc-500">{d.mondo_id}</div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">Fonti</h3>
        <CitationList citations={list} />
      </section>
    </div>
  );
}
