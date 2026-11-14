import { useEffect, useState } from "react";
import { getLiterature, type Literature } from "../api/client";
import type { FmaId } from "../types/ids";

const LINK =
  "text-iodine-700 underline decoration-iodine-600/40 underline-offset-2 hover:decoration-iodine-700";

type State =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ok"; data: Literature };

/**
 * Letteratura (Fase 6, tier 2): articoli open access di Europe PMC cercati in tempo
 * reale per nome della struttura. Non sono selezionati né verificati: lo si dice, e
 * ogni articolo porta la sua licenza e il link alla fonte.
 */
export function LiteratureList({ id }: { id: FmaId }) {
  const [result, setResult] = useState<State>({ state: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    setResult({ state: "loading" });
    getLiterature(id, ctrl.signal)
      .then((data) => setResult({ state: "ok", data }))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) {
          setResult({ state: "error", message: e instanceof Error ? e.message : String(e) });
        }
      });
    return () => ctrl.abort();
  }, [id]);

  if (result.state === "loading") {
    return <p className="mt-3 text-[0.85rem] text-ink-mute">Cerco su Europe PMC…</p>;
  }
  if (result.state === "error") {
    return (
      <p className="mt-3 text-[0.85rem] text-ink-soft">
        Europe PMC non risponde ora ({result.message}). Riprova più tardi.
      </p>
    );
  }
  const { articles, total } = result.data;
  return (
    <div>
      <p className="mt-3 text-[0.8rem] text-ink-mute">
        Articoli open access da Europe PMC che nominano questa struttura nel titolo o nell'abstract
        ({total.toLocaleString("it-IT")} in tutto), i più pertinenti prima. Cercati ora, non
        selezionati né verificati.
      </p>
      {articles.length === 0 ? (
        <p className="mt-3 text-[0.85rem] text-ink-soft">Nessun articolo open access trovato.</p>
      ) : (
        <ul className="mt-2">
          {articles.map((a) => (
            <li key={a.id} className="border-b border-gauze-200 py-2">
              <a href={a.citation.url} target="_blank" rel="noreferrer" className={LINK}>
                {a.title}
              </a>
              <div className="mt-0.5 flex flex-wrap gap-x-2 text-[0.76rem] text-ink-mute">
                {a.journal && <span>{a.journal}</span>}
                {a.year && <span>{a.year}</span>}
                <span>{a.citation.license}</span>
                {a.doi && (
                  <a
                    href={`https://doi.org/${a.doi}`}
                    target="_blank"
                    rel="noreferrer"
                    className={LINK}
                  >
                    DOI
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
