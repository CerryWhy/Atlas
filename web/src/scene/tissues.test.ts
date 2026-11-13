import { describe, expect, it } from "vitest";
import { baseColor, defaultModes, groupOf, nextMode } from "./tissues";

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

  it("il contesto nasce velato e cicla velato → pieno → nascosto", () => {
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
