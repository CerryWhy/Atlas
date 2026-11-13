import { describe, expect, it } from "vitest";
import { fitDistance } from "./CameraRig";

describe("flyTo: distanza dalla struttura", () => {
  it("la camera resta fuori dalla sfera della struttura (nessuna compenetrazione)", () => {
    for (const r of [0.004, 0.03, 0.15, 0.8]) {
      expect(fitDistance(r, 30, 1.6)).toBeGreaterThan(r);
    }
  });

  it("cresce col raggio: strutture grandi si guardano da più lontano", () => {
    expect(fitDistance(0.2, 30, 1)).toBeGreaterThan(fitDistance(0.05, 30, 1));
  });

  it("in una vista stretta si allontana per far stare la sfera in larghezza", () => {
    expect(fitDistance(0.1, 30, 0.5)).toBeGreaterThan(fitDistance(0.1, 30, 2));
  });

  it("non si avvicina oltre la distanza minima", () => {
    expect(fitDistance(0.0001, 30, 1)).toBeCloseTo(0.04);
  });
});
