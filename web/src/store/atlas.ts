import { create } from "zustand";
import {
  getStructure,
  postLocate,
  type Located,
  type MeshFile,
  type MeshNode,
  type Structure,
} from "../api/client";
import {
  DEFAULT_LEVEL,
  defaultModes,
  groupOf,
  nextMode,
  peel,
  type GroupKey,
  type Level,
  type Mode,
} from "../scene/tissues";
import type { FmaId } from "../types/ids";

/** Un nodo del GLB arricchito con il suo gruppo di resa. */
export type SceneNode = MeshNode & { group: GroupKey };

type Detail =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ok"; data: Structure };

type LocateState =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ok"; data: Located };

/** Dove la camera deve volare quando non c'è una scheda aperta (es. risultati di /locate). */
export type Aim = { id: string; c: [number, number, number]; r: number } | null;

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
  /** Livello del comando a strati; null quando un gruppo è stato cambiato a mano. */
  level: Level | null;
  /** Risultati di "dal sintomo al corpo": restano finché non se ne chiede un altro. */
  located: LocateState;
  aim: Aim;
  /** "Mostra solo questo": tutto ciò che non è acceso dalla selezione sparisce. */
  isolated: boolean;

  setScene: (regions: MeshFile[], nodes: MeshNode[]) => void;
  select: (id: FmaId | null) => void;
  hover: (node: FmaId | null) => void;
  cycleMode: (group: GroupKey) => void;
  setLevel: (level: Level) => void;
  toggleIsolated: () => void;
  locate: (text: string) => void;
  clearLocated: () => void;
};

/** I nodi da accendere per un risultato di /locate: tutte le strutture trovate. */
function locatedNodes(data: Located): ReadonlySet<FmaId> {
  return new Set(data.structures.flatMap((s) => s.mesh_nodes));
}

function aimAt(data: Located): Aim {
  const first = data.structures.find((s) => s.centroid && s.radius);
  return first?.centroid && first.radius
    ? { id: first.fma_id, c: first.centroid as [number, number, number], r: first.radius }
    : null;
}

let locating: AbortController | null = null;

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
  level: DEFAULT_LEVEL,
  isolated: false,
  located: { state: "idle" },
  aim: null,

  setScene: (regions, nodes) =>
    set({
      regions,
      nodes: new Map(
        nodes.map(
          (n) => [n.fma_id, { ...n, group: groupOf(n.system, n.label_en, n.tissue) }] as const,
        ),
      ),
    }),

  select: (id) => {
    inflight?.abort();
    inflight = null;
    if (id === null) {
      // chiusa la scheda si torna ai risultati di /locate, se ci sono, ancora accesi
      const located = get().located;
      set({
        selected: null,
        detail: { state: "idle" },
        lit: located.state === "ok" ? locatedNodes(located.data) : EMPTY,
        isolated: false,
      });
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
        set({
          detail: {
            state: "error",
            message: e instanceof Error ? e.message : String(e),
          },
        });
      });
  },

  hover: (node) => {
    if (node === get().hovered) return;
    set({
      hovered: node,
      hoveredFocus: node ? (get().nodes.get(node)?.focus_fma_id ?? node) : null,
    });
  },

  locate: (text) => {
    locating?.abort();
    const ctrl = new AbortController();
    locating = ctrl;
    get().select(null);
    set({ located: { state: "loading" }, aim: null });
    postLocate(text, ctrl.signal)
      .then((data) => {
        if (locating !== ctrl) return;
        set({ located: { state: "ok", data }, lit: locatedNodes(data), aim: aimAt(data) });
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        set({ located: { state: "error", message: e instanceof Error ? e.message : String(e) } });
      });
  },

  clearLocated: () => {
    locating?.abort();
    locating = null;
    set({ located: { state: "idle" }, aim: null, lit: get().selected ? get().lit : EMPTY });
  },

  toggleIsolated: () => set((s) => ({ isolated: s.selected !== null && !s.isolated })),

  cycleMode: (group) =>
    set((s) => ({
      modes: { ...s.modes, [group]: nextMode(group, s.modes[group]) },
      level: null,
    })),

  setLevel: (level) => set({ modes: peel(level), level }),
}));
