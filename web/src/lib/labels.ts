// Nomi mostrati all'utente. Le etichette italiane arrivano da FMA o, dove FMA non le ha,
// da Wikidata (voce con lo stesso FMA ID, citata nella scheda); altrimenti si mostra il
// nome inglese (non si traduce a mano: I5).

type Named = { label_en: string; label_it?: string | null };

export const displayName = (s: Named): string => capitalize(s.label_it ?? s.label_en);

export function capitalize(s: string): string {
  return s.length > 0 ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

const REGION_NAMES: Record<string, string> = {
  abdomen: "Addome",
  thorax: "Torace",
  pelvis: "Pelvi",
  head: "Testa",
  neck: "Collo",
  upper_limb: "Arto superiore",
  lower_limb: "Arto inferiore",
};

export const regionName = (key: string | null | undefined): string =>
  key ? (REGION_NAMES[key] ?? capitalize(key)) : "Atlante";

/** Nome della scena: la regione se è una sola, il corpo se sono più d'una. */
export const sceneName = (regions: readonly { region?: string | null }[]): string =>
  regions.length === 1 ? regionName(regions[0]?.region) : regions.length > 1 ? "Corpo umano" : "Atlante";

/** 'FMA:7197' → 'FMA 7197' (più leggibile nei testi; l'ID resta quello). */
export const spellId = (curie: string): string => curie.replace(":", " ");
