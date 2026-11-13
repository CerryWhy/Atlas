import { useEffect, useState } from "react";
import { getRegions, type MeshFile } from "./api/client";
import { Attribution } from "./pages/Attribution";
import { StructurePanel } from "./panels/StructurePanel";
import { Atlas } from "./scene/Atlas";

function Main() {
  const [regions, setRegions] = useState<MeshFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getRegions(ctrl.signal)
      .then(setRegions)
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setError(String(e));
      });
    return () => ctrl.abort();
  }, []);

  return (
    <div className="flex h-full flex-col bg-zinc-950 text-zinc-200">
      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          {error ? <p className="p-4 text-red-400">{error}</p> : <Atlas regions={regions} />}
        </div>
        <aside className="w-96 shrink-0 overflow-y-auto border-l border-zinc-800 p-5">
          <StructurePanel />
        </aside>
      </div>
      <footer className="flex items-center justify-between gap-4 border-t border-zinc-800 px-4 py-2 text-xs text-zinc-500">
        <span>
          Strumento di studio anatomico e fisiopatologico. Non destinato all'uso clinico su
          persone.
        </span>
        <a href="/attribution" className="shrink-0 text-sky-400 hover:underline">
          Fonti e attribuzioni
        </a>
      </footer>
    </div>
  );
}

export function App() {
  return window.location.pathname === "/attribution" ? <Attribution /> : <Main />;
}
