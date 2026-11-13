import { useMemo } from "react";
import { useAtlasStore } from "../store/atlas";
import { GROUP_ORDER, GROUPS, type GroupKey, type Mode } from "../scene/tissues";

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

/** Legenda della tavola: ogni voce accende, vela o spegne un gruppo di strutture. */
export function LayerControls() {
  const nodes = useAtlasStore((s) => s.nodes);
  const modes = useAtlasStore((s) => s.modes);
  const cycle = useAtlasStore((s) => s.cycleMode);

  const present = useMemo(() => {
    const count = new Map<GroupKey, number>();
    for (const n of nodes.values()) count.set(n.group, (count.get(n.group) ?? 0) + 1);
    return GROUP_ORDER.filter((g) => count.has(g)).map((g) => ({ key: g, n: count.get(g) ?? 0 }));
  }, [nodes]);

  if (present.length === 0) return null;

  return (
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
  );
}
