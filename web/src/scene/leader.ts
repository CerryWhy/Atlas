/**
 * Ponte tra la scena (che sa dove cade sullo schermo la struttura selezionata)
 * e la linea di richiamo disegnata in SVG sopra la pagina. Passa un punto a ogni
 * frame senza attraversare React: nessun re-render durante la rotazione.
 */
export type ScreenPoint = { x: number; y: number };
type Listener = (p: ScreenPoint | null) => void;

let listener: Listener | null = null;

export const leaderBus = {
  publish(p: ScreenPoint | null): void {
    listener?.(p);
  },
  subscribe(l: Listener): () => void {
    listener = l;
    return () => {
      if (listener === l) listener = null;
    };
  },
};

export const prefersReducedMotion = (): boolean =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
