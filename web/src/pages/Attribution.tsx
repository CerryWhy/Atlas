import { useEffect, useState } from "react";
import { getAttribution, type SourceRelease } from "../api/client";

/** /attribution — attribuzioni obbligatorie (SPEC §7), lette da atlas.db. */
export function Attribution() {
  const [rows, setRows] = useState<SourceRelease[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getAttribution(ctrl.signal)
      .then(setRows)
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setError(String(e));
      });
    return () => ctrl.abort();
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-4 py-10 text-zinc-200">
      <a href="/" className="text-sm text-sky-400 hover:underline">
        ← Torna all'atlante
      </a>
      <h1 className="mt-4 text-2xl font-semibold">Fonti e attribuzioni</h1>
      {error && <p className="mt-4 text-red-400">{error}</p>}
      <ul className="mt-6 space-y-4">
        {rows?.map((r) => (
          <li key={r.source} className="rounded-md bg-zinc-800/60 p-4">
            <p>{r.attribution}</p>
            <p className="mt-1 text-xs text-zinc-400">
              <a href={r.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
                {r.title}
              </a>{" "}
              · versione {r.version} · {r.license}
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
