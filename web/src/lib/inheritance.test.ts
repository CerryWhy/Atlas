import { describe, expect, it } from "vitest";
import type { InheritedLink } from "../api/client";
import { inheritanceKind, inheritanceSentence } from "./inheritance";

const link = (basis: string, carries_content: boolean): InheritedLink => ({
  uberon_id: "UBERON:9999999",
  basis,
  unsided_label: "x",
  carries_content,
  citations: [],
});

describe("voci ereditate", () => {
  it("non c'è nota se nessun legame porta contenuto", () => {
    expect(inheritanceKind([])).toBeNull();
    expect(inheritanceKind([link("fma_laterality", false)])).toBeNull();
  });

  it("distingue il lato dalla classe più generale", () => {
    expect(inheritanceKind([link("fma_laterality", true)])).toBe("side");
    expect(inheritanceKind([link("uberon_laterality", true), link("fma_is_a", false)])).toBe(
      "side",
    );
    expect(inheritanceKind([link("fma_is_a", true)])).toBe("class");
  });

  it("dichiara sempre che le voci non sono specifiche", () => {
    expect(inheritanceSentence("class", true)).toContain("non specificamente per questa struttura");
    expect(inheritanceSentence("side", false)).toContain("«senza lato»");
  });
});
