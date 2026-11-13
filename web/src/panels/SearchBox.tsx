import { useId, useMemo, useState } from "react";
import { displayName } from "../lib/labels";
import { useAtlasStore } from "../store/atlas";
import type { FmaId } from "../types/ids";

type Entry = { id: FmaId; name: string; latin: string | null; partOf: string | null; hay: string };

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

/** Cerca una struttura per nome (italiano, inglese o latino) tra quelle in scena. */
export function SearchBox() {
  const nodes = useAtlasStore((s) => s.nodes);
  const select = useAtlasStore((s) => s.select);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();

  const index = useMemo(() => {
    const out = new Map<FmaId, Entry>();
    for (const n of nodes.values()) {
      const focusName = displayName({ label_en: n.focus_label_en, label_it: n.focus_label_it });
      // l'organo "di fuoco" è cercabile anche se non ha un nodo proprio (es. fegato)
      if (!out.has(n.focus_fma_id)) {
        out.set(n.focus_fma_id, {
          id: n.focus_fma_id,
          name: focusName,
          latin: null,
          partOf: null,
          hay: norm(`${n.focus_label_en} ${n.focus_label_it ?? ""}`),
        });
      }
      const own = out.get(n.fma_id);
      const entry: Entry = {
        id: n.fma_id,
        name: displayName(n),
        latin: n.label_la ?? null,
        partOf: n.focus_fma_id !== n.fma_id ? focusName : null,
        hay: norm(`${n.label_en} ${n.label_it ?? ""} ${n.label_la ?? ""}`),
      };
      if (!own || own.latin === null) out.set(n.fma_id, entry);
    }
    return [...out.values()].sort((a, b) => a.name.localeCompare(b.name, "it"));
  }, [nodes]);

  const q = norm(query.trim());
  const results = useMemo(() => {
    if (q.length < 2) return [];
    const starts = index.filter((e) => e.hay.startsWith(q) || e.hay.includes(` ${q}`));
    const rest = index.filter((e) => !starts.includes(e) && e.hay.includes(q));
    return [...starts, ...rest].slice(0, 8);
  }, [index, q]);

  const choose = (e: Entry) => {
    select(e.id);
    setQuery("");
    setActive(0);
  };

  return (
    <div className="relative">
      <label htmlFor={`${listId}-input`} className="sr-only">
        Cerca una struttura
      </label>
      <input
        id={`${listId}-input`}
        type="search"
        role="combobox"
        aria-expanded={results.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        spellCheck={false}
        placeholder="Cerca una struttura: fegato, stomach, hepar…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            const hit = results[active];
            if (hit) choose(hit);
          } else if (e.key === "Escape") {
            setQuery("");
          }
        }}
        className="w-full border-0 border-b border-gauze-300 bg-transparent px-0 py-2 text-[0.95rem] text-ink placeholder:text-ink-mute focus:border-iodine-600 focus:outline-none"
      />
      {q.length >= 2 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute inset-x-0 top-full z-10 max-h-72 overflow-y-auto border border-t-0 border-gauze-300 bg-gauze-50 shadow-lg"
        >
          {results.length === 0 && (
            <li className="px-3 py-2 text-[0.88rem] text-ink-mute">
              Nessuna struttura in scena con questo nome.
            </li>
          )}
          {results.map((e, i) => (
            <li key={e.id} role="option" aria-selected={i === active}>
              <button
                type="button"
                onClick={() => choose(e)}
                onPointerEnter={() => setActive(i)}
                className={`block w-full cursor-pointer px-3 py-1.5 text-left ${
                  i === active ? "bg-iodine-100" : ""
                }`}
              >
                <span className="font-serif text-[1rem]">{e.name}</span>
                {e.latin && <span className="ml-2 font-serif italic text-ink-mute">{e.latin}</span>}
                {e.partOf && (
                  <span className="block text-[0.78rem] text-ink-mute">parte di {e.partOf}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
