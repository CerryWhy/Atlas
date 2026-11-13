import { describe, expect, it } from "vitest";
import { shortVersion } from "../panels/CitationList";
import { displayName, regionName, spellId } from "./labels";

describe("nomi mostrati", () => {
  it("preferisce l'italiano quando la fonte lo dà, altrimenti l'inglese", () => {
    expect(displayName({ label_en: "Liver", label_it: "Fegato" })).toBe("Fegato");
    expect(displayName({ label_en: "left lobe of liver", label_it: null })).toBe(
      "Left lobe of liver",
    );
  });

  it("nomina le regioni e non inventa quelle che non conosce", () => {
    expect(regionName("abdomen")).toBe("Addome");
    expect(regionName("mediastinum")).toBe("Mediastinum");
    expect(regionName(null)).toBe("Atlante");
  });

  it("rende leggibili ID e versioni senza alterarli", () => {
    expect(spellId("FMA:7197")).toBe("FMA 7197");
    expect(shortVersion("uberon/releases/2026-11-05/uberon-basic.owl")).toBe("2026-11-05");
    expect(shortVersion("5.1.0")).toBe("5.1.0");
  });
});
