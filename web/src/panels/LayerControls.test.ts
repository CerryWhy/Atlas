import { describe, expect, it } from "vitest";
import { availableLevels } from "./LayerControls";

describe("comando a strati", () => {
  it("mostra solo i livelli che hanno strutture in scena, più gli organi", () => {
    expect(availableLevels(new Set(["skin", "muscles", "bones", "digestive"]))).toEqual([
      "skin",
      "muscles",
      "bones",
      "organs",
    ]);
    expect(availableLevels(new Set(["muscles", "digestive"]))).toEqual(["muscles", "organs"]);
    expect(availableLevels(new Set(["digestive"]))).toEqual(["organs"]);
  });
});
