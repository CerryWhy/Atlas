import { Color } from "three";

/**
 * Gruppi di resa: come una struttura viene colorata e in che modalità compare.
 * È una scelta puramente grafica: non identifica mai una struttura (quello lo fa
 * l'FMA ID) e non dipende dalla regione caricata.
 */
export type GroupKey =
  | "digestive"
  | "biliary"
  | "arterial"
  | "venous"
  | "urinary"
  | "endocrine"
  | "genital"
  | "respiratory"
  | "nervous"
  | "skin"
  | "muscles"
  | "bones"
  | "frame";

export type Mode = "solid" | "ghost" | "hidden";

type Group = {
  label: string;
  color: string;
  /** Le strutture di contesto (parete, scheletro) nascono trasparenti e non cliccabili. */
  modes: readonly Mode[];
};

export const GROUPS: Record<GroupKey, Group> = {
  digestive: {
    label: "Organi digerenti",
    color: "#c9826b",
    modes: ["solid", "hidden"],
  },
  biliary: {
    label: "Vie biliari",
    color: "#a3b04c",
    modes: ["solid", "hidden"],
  },
  arterial: { label: "Arterie", color: "#b8362f", modes: ["solid", "hidden"] },
  venous: { label: "Vene", color: "#4f6fae", modes: ["solid", "hidden"] },
  urinary: {
    label: "Apparato urinario",
    color: "#9c4f3a",
    modes: ["solid", "hidden"],
  },
  endocrine: {
    label: "Ghiandole endocrine",
    color: "#d8a545",
    modes: ["solid", "hidden"],
  },
  genital: {
    label: "Apparato genitale",
    color: "#c58fa3",
    modes: ["solid", "hidden"],
  },
  respiratory: {
    label: "Vie respiratorie",
    color: "#d7a9a4",
    modes: ["solid", "hidden"],
  },
  nervous: {
    label: "Sistema nervoso",
    color: "#e0cf8a",
    modes: ["solid", "hidden"],
  },
  skin: {
    label: "Pelle",
    color: "#e3b9a0",
    modes: ["ghost", "solid", "hidden"],
  },
  muscles: {
    label: "Muscoli e tendini",
    color: "#b0645a",
    modes: ["ghost", "solid", "hidden"],
  },
  bones: {
    label: "Ossa e cartilagini",
    color: "#e9e2cf",
    modes: ["ghost", "solid", "hidden"],
  },
  frame: {
    label: "Parete e altro",
    color: "#d9d3c4",
    modes: ["ghost", "solid", "hidden"],
  },
};

export const GROUP_ORDER = Object.keys(GROUPS) as GroupKey[];

/** Gruppi di contesto, dal più esterno al più interno. Tutti gli altri sono organi. */
export const CONTEXT_LAYERS = ["skin", "muscles", "bones", "frame"] as const;
const isContext = (g: GroupKey): boolean => (CONTEXT_LAYERS as readonly GroupKey[]).includes(g);

/** Livelli del comando a strati: pelle → muscoli → ossa → organi. */
export type Level = "skin" | "muscles" | "bones" | "organs";
export const LEVELS: readonly Level[] = ["skin", "muscles", "bones", "organs"];
export const LEVEL_LABEL: Record<Level, string> = {
  skin: "Pelle",
  muscles: "Muscoli",
  bones: "Ossa",
  organs: "Organi",
};

/**
 * Modalità dei gruppi quando si "scende" a un livello: ciò che sta sopra sparisce, il
 * livello scelto è pieno, ciò che sta sotto resta velato per orientarsi; gli organi
 * sono sempre pieni. Al livello "organi" restano velati solo ossa e parete, come
 * riferimento.
 */
export function peel(level: Level): Record<GroupKey, Mode> {
  const outerToInner: readonly GroupKey[] = ["skin", "muscles", "bones"];
  const at = level === "organs" ? outerToInner.length : outerToInner.indexOf(level);
  const layer = (g: GroupKey): Mode => {
    if (g === "frame") return "ghost";
    if (level === "organs" && g === "bones") return "ghost";
    const i = outerToInner.indexOf(g);
    return i < at ? "hidden" : i === at ? "solid" : "ghost";
  };
  return Object.fromEntries(
    GROUP_ORDER.map((g) => [g, isContext(g) ? layer(g) : "solid"]),
  ) as Record<GroupKey, Mode>;
}

/** All'apertura si guardano gli organi, con ossa e parete velate attorno. */
export const DEFAULT_LEVEL: Level = "organs";
export const defaultModes = (): Record<GroupKey, Mode> => peel(DEFAULT_LEVEL);

export function nextMode(group: GroupKey, current: Mode): Mode {
  const cycle = GROUPS[group].modes;
  return cycle[(cycle.indexOf(current) + 1) % cycle.length] ?? "solid";
}

const SYSTEM_GROUP: Record<string, GroupKey> = {
  digestive: "digestive",
  cardiovascular: "arterial",
  urinary: "urinary",
  endocrine: "endocrine",
  genital: "genital",
  respiratory: "respiratory",
  nervous: "nervous",
};

const TISSUE_GROUP: Record<string, GroupKey> = {
  skin: "skin",
  muscle: "muscles",
  bone: "bones",
};

/**
 * Il tessuto (pelle, muscolo, osso) arriva dalla pipeline, che lo legge dalla
 * tassonomia FMA. Vasi e vie biliari attraversano i sistemi (un'arteria epatica è
 * "nel" fegato): per la tinta guardiamo anche il nome. Solo cosmetica: se il nome non
 * dice nulla, vale il sistema.
 */
export function groupOf(
  system: string | null | undefined,
  labelEn: string,
  tissue?: string | null,
): GroupKey {
  if (tissue && TISSUE_GROUP[tissue]) return TISSUE_GROUP[tissue];
  const name = labelEn.toLowerCase();
  if (/\b(biliary|bile duct|hepatic duct|cystic duct|gallbladder)\b/.test(name)) return "biliary";
  if (/\b(vein|veins|venous|vena)\b/.test(name)) return "venous";
  if (/\b(artery|arteries|arterial|aorta)\b/.test(name)) return "arterial";
  return (system && SYSTEM_GROUP[system]) || "frame";
}

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 0xffffffff;
}

/**
 * Tinta di base di un nodo: il colore del gruppo, variato appena per "organo"
 * (la struttura di fuoco), così fegato e stomaco non si confondono.
 */
export function baseColor(group: GroupKey, focusId: string): Color {
  const c = new Color(GROUPS[group].color);
  if (isContext(group)) return c;
  const t = hash(focusId);
  const u = hash(focusId + "#");
  return c.offsetHSL((t - 0.5) * 0.045, (u - 0.5) * 0.12, (u - 0.5) * 0.11);
}

export const DRAPE_SHADE = new Color("#1a3a36");
