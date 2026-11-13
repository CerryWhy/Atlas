import type { InheritedLink } from "../api/client";

/**
 * Da dove arrivano le voci ereditate di una scheda.
 * - "side":  dalla versione senza lato ("Right humerus" → "Humerus");
 * - "class": dall'antenato FMA più vicino descritto dalle fonti ("Right fourth rib" → "Rib").
 * La pipeline usa "class" solo quando lato ed esatto non portano nulla, quindi i legami
 * che portano contenuto in una scheda sono tutti dello stesso tipo.
 */
export type InheritanceKind = "side" | "class";

export function contentLinks(links: InheritedLink[]): InheritedLink[] {
  return links.filter((l) => l.carries_content);
}

export function inheritanceKind(links: InheritedLink[]): InheritanceKind | null {
  const carrying = contentLinks(links);
  if (carrying.length === 0) return null;
  return carrying.every((l) => l.basis === "fma_is_a") ? "class" : "side";
}

/** Testo della nota dopo l'elenco dei concetti generali citati. */
export function inheritanceSentence(kind: InheritanceKind, all: boolean): string {
  if (kind === "class") {
    return (
      ", di cui questa struttura è un tipo particolare, ma non la descrivono in modo specifico. " +
      "Le voci qui sotto valgono per la classe più generale, non specificamente per questa struttura."
    );
  }
  return (
    " senza distinguere il lato. " +
    (all
      ? "Le voci qui sotto valgono per la struttura in generale, non specificamente per questo lato."
      : "Le voci segnate «senza lato» valgono per la struttura in generale, non specificamente per questo lato.")
  );
}
