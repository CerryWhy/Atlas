import { describe, expect, it } from "vitest";
import { asFmaId, isFmaId, isMondoId } from "./ids";

describe("branded ids", () => {
  it("accetta solo CURIE FMA", () => {
    expect(isFmaId("FMA:7197")).toBe(true);
    expect(isFmaId("FMA7197")).toBe(false);
    expect(isFmaId("liver")).toBe(false);
    expect(() => asFmaId("fegato")).toThrow();
  });

  it("valida MONDO a 7 cifre", () => {
    expect(isMondoId("MONDO:0002691")).toBe(true);
    expect(isMondoId("MONDO:2691")).toBe(false);
  });
});
