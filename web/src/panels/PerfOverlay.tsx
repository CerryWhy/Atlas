import { useEffect, useState } from "react";
import {
  FLUID_FPS,
  perf,
  perfEnabled,
  TARGET_FPS,
  TARGET_LOAD_S,
  type PerfStats,
} from "../scene/perf";
import { useAtlasStore } from "../store/atlas";

function Verdict({ ok }: { ok: boolean | null }) {
  if (ok === null) return null;
  return <span className={ok ? "text-emerald-300" : "text-red-300"}>{ok ? " ✓" : " ✗"}</span>;
}

/**
 * Riquadro di misura per l'accettazione della Fase 2 (`?perf` nell'indirizzo):
 * tempo di caricamento, fps e scatti, da confrontare con gli obiettivi della SPEC.
 */
export function PerfOverlay() {
  const [enabled] = useState(() => perfEnabled());
  const [stats, setStats] = useState<PerfStats>(() => perf.stats());
  const count = useAtlasStore((s) => s.nodes.size);

  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setStats(perf.stats()), 500);
    return () => window.clearInterval(id);
  }, [enabled]);

  if (!enabled) return null;
  const { loadS, fps, p95Ms } = stats;
  return (
    <div
      role="status"
      className="pointer-events-none absolute left-5 top-24 z-10 rounded-sm bg-black/60 px-2.5 py-1.5 font-mono text-[0.72rem] leading-relaxed text-mist"
    >
      <div>
        caricamento {loadS === null ? "…" : `${loadS.toFixed(2)} s`} (obiettivo &lt; {TARGET_LOAD_S}{" "}
        s, {count} nodi)
        <Verdict ok={loadS === null ? null : loadS < TARGET_LOAD_S} />
      </div>
      <div>
        {fps === null ? "…" : `${fps.toFixed(0)} fps`} · p95{" "}
        {p95Ms === null ? "…" : `${p95Ms.toFixed(1)} ms`} (obiettivo {TARGET_FPS} fps)
        <Verdict ok={fps === null ? null : fps >= FLUID_FPS} />
      </div>
      <div className="text-mist-dim">ruota e ingrandisci la scena mentre misuri</div>
    </div>
  );
}
