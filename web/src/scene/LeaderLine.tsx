import { useEffect, useRef } from "react";
import { useAtlasStore } from "../store/atlas";
import { leaderBus } from "./leader";

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

/**
 * Linea di richiamo: dalla struttura selezionata al suo nome sulla scheda, come
 * nelle tavole a stampa. Vive in un SVG sopra la pagina e viene aggiornata
 * direttamente a ogni frame dalla scena (vedi leaderBus), senza re-render.
 */
export function LeaderLine() {
  const selected = useAtlasStore((s) => s.selected);
  const svg = useRef<SVGSVGElement>(null);
  const path = useRef<SVGPathElement>(null);
  const dot = useRef<SVGCircleElement>(null);
  const ring = useRef<SVGCircleElement>(null);

  useEffect(
    () =>
      leaderBus.subscribe((p) => {
        const root = svg.current;
        const anchor = document.querySelector<HTMLElement>("[data-leader-anchor]");
        const sheet = anchor?.closest<HTMLElement>("[data-sheet]");
        if (!root || !path.current || !dot.current || !ring.current) return;
        if (!p || !anchor || !sheet) {
          root.style.visibility = "hidden";
          return;
        }
        const stage = root.getBoundingClientRect();
        const a = anchor.getBoundingClientRect();
        const s = sheet.getBoundingClientRect();

        let d: string;
        if (s.left - stage.left > p.x + 48) {
          // scheda a lato: obliqua, poi un tratto orizzontale fino al nome
          const ex = s.left - stage.left;
          const ey = clamp(a.top + a.height * 0.55, s.top + 20, s.bottom - 20) - stage.top;
          d = `M${p.x},${p.y} L${ex - 30},${ey} L${ex},${ey}`;
        } else {
          // scheda in basso (schermi stretti): si scende sul suo bordo
          const ex = clamp(p.x, s.left + 24, s.right - 24) - stage.left;
          d = `M${p.x},${p.y} L${ex},${s.top - stage.top}`;
        }
        path.current.setAttribute("d", d);
        for (const c of [dot.current, ring.current]) {
          c.setAttribute("cx", String(p.x));
          c.setAttribute("cy", String(p.y));
        }
        root.style.visibility = "visible";
      }),
    [],
  );

  return (
    <svg
      ref={svg}
      key={selected ?? "none"}
      className="leader draw pointer-events-none absolute inset-0 h-full w-full"
      style={{ visibility: "hidden" }}
      aria-hidden="true"
    >
      <path ref={path} pathLength={1} />
      <circle ref={ring} className="ring" r={7} />
      <circle ref={dot} className="dot" r={3} />
    </svg>
  );
}
