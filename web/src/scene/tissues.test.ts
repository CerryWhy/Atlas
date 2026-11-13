import { describe, expect, it } from "vitest";
import { baseColor, defaultModes, groupOf, nextMode, peel } from "./tissues";

describe("gruppi di resa", () => {
  it("riconosce vasi e vie biliari dal nome, qualunque sia il sistema", () => {
    expect(groupOf("digestive", "Right hepatic artery")).toBe("arterial");
    expect(groupOf("digestive", "Left portal vein")).toBe("venous");
    expect(groupOf("cardiovascular", "Inferior vena cava")).toBe("venous");
    expect(groupOf("digestive", "Common hepatic duct")).toBe("biliary");
    expect(groupOf("digestive", "Gallbladder")).toBe("biliary");
  });

  it("altrimenti segue il sistema, e senza sistema è contesto", () => {
    expect(groupOf("digestive", "Stomach")).toBe("digestive");
    expect(groupOf("urinary", "Right kidney")).toBe("urinary");
    expect(groupOf("cardiovascular", "Celiac trunk")).toBe("arterial");
    expect(groupOf(null, "Left external oblique")).toBe("frame");
    expect(groupOf("musculoskeletal", "Sacrum")).toBe("frame");
  });

  it("il tessuto dichiarato dalla pipeline viene prima del nome e del sistema", () => {
    expect(groupOf("musculoskeletal", "Right biceps brachii", "muscle")).toBe("muscles");
    expect(groupOf("musculoskeletal", "Sacrum", "bone")).toBe("bones");
    expect(groupOf(null, "Skin of abdomen", "skin")).toBe("skin");
    expect(groupOf("musculoskeletal", "Sacrum", null)).toBe("frame");
    expect(groupOf("musculoskeletal", "Sacrum", "unknown")).toBe("frame");
  });

  it("gli strati tolgono ciò che sta sopra e velano ciò che sta sotto", () => {
    const skin = peel("skin");
    expect([skin.skin, skin.muscles, skin.bones]).toEqual(["solid", "ghost", "ghost"]);
    const muscles = peel("muscles");
    expect([muscles.skin, muscles.muscles, muscles.bones]).toEqual(["hidden", "solid", "ghost"]);
    const bones = peel("bones");
    expect([bones.skin, bones.muscles, bones.bones]).toEqual(["hidden", "hidden", "solid"]);
    const organs = peel("organs");
    expect([organs.skin, organs.muscles, organs.bones]).toEqual(["hidden", "hidden", "ghost"]);
    for (const level of ["skin", "muscles", "bones", "organs"] as const) {
      expect(peel(level).digestive).toBe("solid"); // gli organi restano sempre pieni
      expect(peel(level).frame).toBe("ghost");
    }
  });

  it("il contesto nasce velato e cicla velato → pieno → nascosto", () => {
    expect(defaultModes()).toEqual(peel("organs"));
    expect(defaultModes().frame).toBe("ghost");
    expect(defaultModes().digestive).toBe("solid");
    expect(nextMode("frame", "ghost")).toBe("solid");
    expect(nextMode("frame", "solid")).toBe("hidden");
    expect(nextMode("frame", "hidden")).toBe("ghost");
    expect(nextMode("digestive", "solid")).toBe("hidden");
    expect(nextMode("digestive", "hidden")).toBe("solid");
  });

  it("la tinta è stabile per organo e distingue organi diversi", () => {
    const liver = baseColor("digestive", "FMA:7197").getHexString();
    expect(baseColor("digestive", "FMA:7197").getHexString()).toBe(liver);
    expect(baseColor("digestive", "FMA:7148").getHexString()).not.toBe(liver);
  });
});
