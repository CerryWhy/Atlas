import { describe, expect, it } from "vitest";
import { perfEnabled, summarize } from "./perf";

describe("misure di Fase 2", () => {
  it("si attivano solo con ?perf", () => {
    expect(perfEnabled("?perf")).toBe(true);
    expect(perfEnabled("?x=1&perf=1")).toBe(true);
    expect(perfEnabled("")).toBe(false);
    expect(perfEnabled("?performance")).toBe(false);
  });

  it("calcola fps e scatti dalle durate dei frame", () => {
    const steady = Array.from({ length: 120 }, () => 1 / 60);
    const s = summarize(steady);
    expect(s.fps).toBeCloseTo(60, 5);
    expect(s.p95Ms).toBeCloseTo(16.67, 1);
    // pochi frame lenti abbassano poco la media ma si vedono nel 95° percentile
    const janky = [
      ...Array.from({ length: 90 }, () => 1 / 60),
      ...Array.from({ length: 10 }, () => 0.05),
    ];
    expect(summarize(janky).p95Ms).toBeCloseTo(50, 5);
    expect(summarize([])).toEqual({ fps: null, p95Ms: null });
  });
});
