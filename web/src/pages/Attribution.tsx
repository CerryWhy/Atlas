import { useEffect, useState } from "react";
import { getAttribution, type SourceRelease } from "../api/client";
import { shortVersion } from "../panels/CitationList";

/** /attribution — attribuzioni obbligatorie (SPEC §7), lette da atlas.db. */
export function Attribution() {
  const [rows, setRows] = useState<SourceRelease[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getAttribution(ctrl.signal)
      .then(setRows)
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      });
    return () => ctrl.abort();
  }, []);

  return (
    <div className="min-h-full bg-gauze-100">
      <main className="mx-auto max-w-[44rem] px-6 py-12">
        <a
          href="/"
          className="text-[0.88rem] text-iodine-700 underline decoration-iodine-600/40 underline-offset-2 hover:decoration-iodine-700"
        >
          Torna alla tavola
        </a>
        <h1 className="mt-6 font-serif text-[2.6rem] font-medium leading-[1.08] tracking-[-0.015em]">
          Fonti e attribuzioni
        </h1>
        <p className="mt-4 max-w-[60ch] text-ink-soft">
          Ogni forma e ogni voce di Atlas viene da una di queste fonti, usata nei termini della
          sua licenza. Le versioni sono quelle da cui è stato costruito il database in uso.
        </p>

        {error && (
          <p className="mt-8 border-l-2 border-iodine-600 pl-3 text-ink-soft">
            Non riesco a leggere l'elenco dal server. {error}.
          </p>
        )}

        <ul className="mt-10 border-t border-gauze-300">
          {rows?.map((r) => (
            <li key={r.source} className="border-b border-gauze-300 py-5">
              <h2 className="font-serif text-[1.3rem] font-medium">
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline decoration-gauze-300 underline-offset-4 hover:decoration-iodine-600"
                >
                  {r.title}
                </a>
              </h2>
              <p className="mt-1.5 max-w-[62ch] text-ink-soft">{r.attribution}</p>
              <p className="tnum mt-1.5 text-[0.82rem] text-ink-mute">
                Versione {shortVersion(r.version)}
                <span className="mx-2 text-gauze-300" aria-hidden="true">
                  |
                </span>
                {r.license}
              </p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
