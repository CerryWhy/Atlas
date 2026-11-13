import { useProgress } from "@react-three/drei";
import { useEffect, useState } from "react";
import { getRegionNodes, getRegions } from "./api/client";
import { sceneName } from "./lib/labels";
import { Attribution } from "./pages/Attribution";
import { LayerControls } from "./panels/LayerControls";
import { PerfOverlay } from "./panels/PerfOverlay";
import { StructurePanel } from "./panels/StructurePanel";
import { Atlas } from "./scene/Atlas";
import { HoverLabel } from "./scene/HoverLabel";
import { LeaderLine } from "./scene/LeaderLine";
import { useAtlasStore } from "./store/atlas";

function LoadingNote({ ready }: { ready: boolean }) {
  const { active, progress } = useProgress();
  if (ready && !active) return null;
  return (
    <p className="pointer-events-none absolute inset-0 grid place-items-center font-serif text-[1.1rem] italic text-mist-dim">
      {ready ? `Carico la tavola, ${Math.round(progress)}%` : "Carico la tavola"}
    </p>
  );
}

function Main() {
  const setScene = useAtlasStore((s) => s.setScene);
  const regions = useAtlasStore((s) => s.regions);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    (async () => {
      const found = await getRegions(ctrl.signal);
      const nodes = await Promise.all(found.map((r) => getRegionNodes(r.mesh_file, ctrl.signal)));
      setScene(found, nodes.flat());
    })().catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e));
    });
    return () => ctrl.abort();
  }, [setScene]);

  return (
    <div className="stage relative h-full overflow-hidden">
      {/* La scena occupa lo spazio lasciato libero dalla scheda */}
      <div className="absolute inset-x-0 top-[4.5rem] bottom-[calc(var(--sheet-h)+2.25rem)] wide:top-0 wide:bottom-[4.75rem] wide:right-[calc(var(--sheet-w)+1rem)]">
        {error ? (
          <div className="grid h-full place-items-center px-8 text-center text-mist">
            <div>
              <p className="font-serif text-[1.3rem]">La tavola non si è caricata</p>
              <p className="mt-2 max-w-[44ch] text-[0.9rem] text-mist-dim">
                {error}. Controlla che l'API sia avviata e che la pipeline abbia prodotto
                atlas.db, poi ricarica la pagina.
              </p>
            </div>
          </div>
        ) : (
          <>
            <Atlas />
            <LoadingNote ready={regions.length > 0} />
            <PerfOverlay />
          </>
        )}
      </div>

      <LeaderLine />
      <HoverLabel />

      <header className="pointer-events-none absolute inset-x-5 top-4 text-mist wide:right-[calc(var(--sheet-w)+2rem)]">
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-[1.45rem] font-medium tracking-[-0.01em]">Atlas</h1>
          {regions[0] && (
            <span className="font-serif text-[1.05rem] italic text-mist-dim">
              {sceneName(regions)}
            </span>
          )}
        </div>
        {/* Su schermi stretti la legenda sta in alto: sotto, la linea di richiamo scende libera */}
        <div className="pointer-events-auto mt-1 wide:hidden">
          <LayerControls />
        </div>
      </header>

      <footer className="absolute inset-x-5 bottom-[calc(var(--sheet-h)+0.5rem)] wide:bottom-4 wide:right-[calc(var(--sheet-w)+2rem)]">
        <div className="hidden wide:block">
          <LayerControls />
        </div>
        <p className="truncate text-[0.75rem] leading-snug text-mist-dim wide:mt-2 wide:whitespace-normal">
          Strumento di studio anatomico e fisiopatologico, non destinato all'uso clinico su
          persone.{" "}
          <a href="/attribution" className="underline underline-offset-2 hover:text-mist">
            Fonti e attribuzioni
          </a>
        </p>
      </footer>

      <StructurePanel />
    </div>
  );
}

export function App() {
  return window.location.pathname === "/attribution" ? <Attribution /> : <Main />;
}
