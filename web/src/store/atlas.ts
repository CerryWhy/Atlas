import { create } from "zustand";
import { getStructure, type MeshFile, type MeshNode, type Structure } from "../api/client";
import { defaultModes, groupOf, nextMode, type GroupKey, type Mode } from "../scene/tissues";
import type { FmaId } from "../types/ids";

/** Un nodo del GLB arricchito con il suo gruppo di resa. */
export type SceneNode = MeshNode & { group: GroupKey };

type Detail =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ok"; data: Structure };

type AtlasState = {
  regions: MeshFile[];
  nodes: ReadonlyMap<FmaId, SceneNode>;
  /** Struttura selezionata: può essere un nodo o un suo antenato (es. "fegato"). */
  selected: FmaId | null;
  detail: Detail;
  /** Nodi GLB accesi dalla selezione. */
  lit: ReadonlySet<FmaId>;
  /** Nodo sotto il puntatore e struttura che un click selezionerebbe. */
  hovered: FmaId | null;
  hoveredFocus: FmaId | null;
  modes: Record<GroupKey, Mode>;

  setScene: (regions: MeshFile[], nodes: MeshNode[]) => void;
  select: (id: FmaId | null) => void;
  hover: (node: FmaId | null) => void;
  cycleMode: (group: GroupKey) => void;
};

const EMPTY: ReadonlySet<FmaId> = new Set();
let inflight: AbortController | null = null;

export const useAtlasStore = create<AtlasState>()((set, get) => ({
  regions: [],
  nodes: new Map(),
  selected: null,
  detail: { state: "idle" },
  lit: EMPTY,
  hovered: null,
  hoveredFocus: null,
  modes: defaultModes(),

  setScene: (regions, nodes) =>
    set({
      regions,
      nodes: new Map(
        nodes.map((n) => [n.fma_id, { ...n, group: groupOf(n.system, n.label_en) }] as const),
      ),
    }),

  select: (id) => {
    inflight?.abort();
    inflight = null;
    if (id === null) {
      set({ selected: null, detail: { state: "idle" }, lit: EMPTY });
      return;
    }
    if (id === get().selected && get().detail.state !== "error") return;

    // Accensione immediata con ciò che già sappiamo; l'elenco completo arriva dall'API.
    const guess = new Set<FmaId>();
    for (const n of get().nodes.values()) {
      if (n.fma_id === id || n.focus_fma_id === id) guess.add(n.fma_id);
    }
    set({ selected: id, detail: { state: "loading" }, lit: guess });

    const ctrl = new AbortController();
    inflight = ctrl;
    getStructure(id, ctrl.signal)
      .then((data) => {
        if (get().selected !== id) return;
        set({ detail: { state: "ok", data }, lit: new Set(data.mesh_nodes) });
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted || get().selected !== id) return;
        set({ detail: { state: "error", message: e instanceof Error ? e.message : String(e) } });
      });
  },

  hover: (node) => {
    if (node === get().hovered) return;
    set({ hovered: node, hoveredFocus: node ? (get().nodes.get(node)?.focus_fma_id ?? node) : null });
  },

  cycleMode: (group) =>
    set((s) => ({ modes: { ...s.modes, [group]: nextMode(group, s.modes[group]) } })),
}));
