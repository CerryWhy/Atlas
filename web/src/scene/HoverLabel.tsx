import { useEffect, useRef } from "react";
import { displayName } from "../lib/labels";
import { useAtlasStore } from "../store/atlas";

/** Didascalia che segue il puntatore: il nome della parte e l'organo a cui appartiene. */
export function HoverLabel() {
  const node = useAtlasStore((s) => (s.hovered ? s.nodes.get(s.hovered) : undefined));
  const el = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const box = el.current;
      const parent = box?.offsetParent;
      if (!box || !parent) return;
      const r = parent.getBoundingClientRect();
      const x = Math.min(e.clientX - r.left + 16, r.width - box.offsetWidth - 8);
      const y = Math.min(e.clientY - r.top + 18, r.height - box.offsetHeight - 8);
      box.style.transform = `translate(${x}px, ${y}px)`;
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => window.removeEventListener("pointermove", move);
  }, []);

  const name = node ? displayName(node) : "";
  const focus =
    node && node.focus_fma_id !== node.fma_id
      ? displayName({ label_en: node.focus_label_en, label_it: node.focus_label_it })
      : null;

  return (
    <div ref={el} className="hover-label" hidden={!node} role="status">
      <div className="font-serif text-[1.02rem] leading-snug">{name}</div>
      {node?.label_la && (
        <div className="font-serif text-[0.86rem] italic text-mist-dim">{node.label_la}</div>
      )}
      {focus && <div className="mt-0.5 text-[0.78rem] text-mist-dim">parte di {focus}</div>}
    </div>
  );
}
