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
  | "frame";

export type Mode = "solid" | "ghost" | "hidden";

type Group = {
  label: string;
  color: string;
  /** Le strutture di contesto (parete, scheletro) nascono trasparenti e non cliccabili. */
  modes: readonly Mode[];
};

export const GROUPS: Record<GroupKey, Group> = {
  digestive: { label: "Organi digerenti", color: "#c9826b", modes: ["solid", "hidden"] },
  biliary: { label: "Vie biliari", color: "#a3b04c", modes: ["solid", "hidden"] },
  arterial: { label: "Arterie", color: "#b8362f", modes: ["solid", "hidden"] },
  venous: { label: "Vene", color: "#4f6fae", modes: ["solid", "hidden"] },
  urinary: { label: "Apparato urinario", color: "#9c4f3a", modes: ["solid", "hidden"] },
  endocrine: { label: "Ghiandole endocrine", color: "#d8a545", modes: ["solid", "hidden"] },
  genital: { label: "Apparato genitale", color: "#c58fa3", modes: ["solid", "hidden"] },
  respiratory: { label: "Vie respiratorie", color: "#d7a9a4", modes: ["solid", "hidden"] },
  nervous: { label: "Sistema nervoso", color: "#e0cf8a", modes: ["solid", "hidden"] },
  frame: { label: "Parete e scheletro", color: "#e9e2cf", modes: ["ghost", "solid", "hidden"] },
};

export const GROUP_ORDER = Object.keys(GROUPS) as GroupKey[];

export const defaultModes = (): Record<GroupKey, Mode> =>
  Object.fromEntries(GROUP_ORDER.map((k) => [k, GROUPS[k].modes[0]])) as Record<GroupKey, Mode>;

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

/**
 * Vasi e vie biliari attraversano i sistemi (un'arteria epatica è "nel" fegato):
 * per la tinta guardiamo anche il nome. Solo cosmetica: se il nome non dice nulla,
 * vale il sistema.
 */
export function groupOf(system: string | null | undefined, labelEn: string): GroupKey {
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
  if (group === "frame") return c;
  const t = hash(focusId);
  const u = hash(focusId + "#");
  return c.offsetHSL((t - 0.5) * 0.045, (u - 0.5) * 0.12, (u - 0.5) * 0.11);
}

export const DRAPE_SHADE = new Color("#1a3a36");
