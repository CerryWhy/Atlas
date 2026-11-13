/**
 * Misure per il criterio di accettazione della Fase 2 (SPEC §10): strutture caricate
 * in meno di 3 s, interazione a 60 fps. Attive solo con `?perf` nell'indirizzo; vanno
 * lette su uno schermo reale, non in un browser senza GPU.
 */

export const TARGET_LOAD_S = 3;
export const TARGET_FPS = 60;
/** Margine sotto i 60 fps che consideriamo ancora fluido (vsync, misura rumorosa). */
export const FLUID_FPS = 55;

const WINDOW_S = 2;

export type PerfStats = {
  /** Secondi dall'avvio della pagina al primo frame con tutte le regioni caricate. */
  loadS: number | null;
  fps: number | null;
  /** 95° percentile della durata di un frame, in millisecondi: misura gli scatti. */
  p95Ms: number | null;
};

export function perfEnabled(search: string = globalThis.location?.search ?? ""): boolean {
  return new URLSearchParams(search).has("perf");
}

/** Statistiche sugli ultimi `WINDOW_S` secondi di frame (durate in secondi). */
export function summarize(frames: readonly number[]): Pick<PerfStats, "fps" | "p95Ms"> {
  if (frames.length < 2) return { fps: null, p95Ms: null };
  const total = frames.reduce((a, b) => a + b, 0);
  const sorted = [...frames].sort((a, b) => a - b);
  const p95 = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))] ?? 0;
  return { fps: frames.length / total, p95Ms: p95 * 1000 };
}

class PerfRecorder {
  private frames: number[] = [];
  private sum = 0;
  loadS: number | null = null;

  frame(dt: number): void {
    if (!(dt > 0) || dt > 1) return; // scheda in background o primo frame
    this.frames.push(dt);
    this.sum += dt;
    while (this.sum > WINDOW_S && this.frames.length > 1) this.sum -= this.frames.shift() ?? 0;
  }

  loaded(nowMs: number): void {
    this.loadS ??= nowMs / 1000;
  }

  stats(): PerfStats {
    return { loadS: this.loadS, ...summarize(this.frames) };
  }
}

export const perf = new PerfRecorder();
