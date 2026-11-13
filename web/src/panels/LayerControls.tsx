import { useMemo } from "react";
import { useAtlasStore } from "../store/atlas";
import {
  GROUP_ORDER,
  GROUPS,
  LEVEL_LABEL,
  LEVELS,
  type GroupKey,
  type Level,
  type Mode,
} from "../scene/tissues";

const STATE: Record<Mode, string> = {
  solid: "visibile",
  ghost: "in trasparenza",
  hidden: "nascosto",
};

function Swatch({ color, mode }: { color: string; mode: Mode }) {
  return (
    <span
      aria-hidden="true"
      className="relative inline-block size-3 shrink-0 rounded-[2px] border"
      style={{
        borderColor: mode === "hidden" ? "var(--color-mist-dim)" : color,
        background:
          mode === "solid"
            ? color
            : mode === "ghost"
              ? `color-mix(in srgb, ${color} 28%, transparent)`
              : "transparent",
      }}
    />
  );
}

/** I livelli che la scena può mostrare: un livello di contesto senza strutture si salta. */
export function availableLevels(present: ReadonlySet<GroupKey>): Level[] {
  return LEVELS.filter((l) => l === "organs" || present.has(l));
}

/**
 * Comando a strati: pelle → muscoli → ossa → organi. Ciò che sta sopra il livello
 * scelto sparisce, ciò che sta sotto resta velato.
 */
function Peel({ present }: { present: ReadonlySet<GroupKey> }) {
  const level = useAtlasStore((s) => s.level);
  const setLevel = useAtlasStore((s) => s.setLevel);
  const levels = availableLevels(present);
  if (levels.length < 2) return null;
  return (
    <div role="group" aria-label="Strato" className="mb-1.5 flex items-center gap-1 text-[0.82rem]">
      <span className="mr-1 text-mist-dim">Strato</span>
      {levels.map((l, i) => (
        <span key={l} className="flex items-center gap-1">
          {i > 0 && (
            <span aria-hidden="true" className="text-mist-dim">
              →
            </span>
          )}
          <button
            type="button"
            aria-pressed={level === l}
            onClick={() => setLevel(l)}
            className={`cursor-pointer rounded-sm px-1.5 py-0.5 transition-colors hover:text-white ${
              level === l ? "bg-white/15 text-white" : "text-mist"
            }`}
          >
            {LEVEL_LABEL[l]}
          </button>
        </span>
      ))}
    </div>
  );
}

/** Legenda della tavola: ogni voce accende, vela o spegne un gruppo di strutture. */
export function LayerControls() {
  const nodes = useAtlasStore((s) => s.nodes);
  const modes = useAtlasStore((s) => s.modes);
  const cycle = useAtlasStore((s) => s.cycleMode);

  const present = useMemo(() => {
    const count = new Map<GroupKey, number>();
    for (const n of nodes.values()) count.set(n.group, (count.get(n.group) ?? 0) + 1);
    return GROUP_ORDER.filter((g) => count.has(g)).map((g) => ({
      key: g,
      n: count.get(g) ?? 0,
    }));
  }, [nodes]);

  const presentSet = useMemo(() => new Set(present.map((p) => p.key)), [present]);

  if (present.length === 0) return null;

  return (
    <>
      <Peel present={presentSet} />
      <ul
        className="flex gap-x-4 gap-y-1 overflow-x-auto whitespace-nowrap text-[0.82rem] text-mist [scrollbar-width:none] wide:flex-wrap wide:overflow-visible"
        aria-label="Legenda"
      >
        {present.map(({ key, n }) => {
          const mode = modes[key];
          return (
            <li key={key}>
              <button
                type="button"
                onClick={() => cycle(key)}
                title={`${GROUPS[key].label}: ${STATE[mode]} (${n} strutture). Clic per cambiare.`}
                aria-label={`${GROUPS[key].label}, ${STATE[mode]}`}
                className={`flex cursor-pointer items-center gap-1.5 py-0.5 transition-colors hover:text-white ${
                  mode === "hidden" ? "text-mist-dim line-through decoration-mist-dim/60" : ""
                }`}
              >
                <Swatch color={GROUPS[key].color} mode={mode} />
                {GROUPS[key].label}
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}
