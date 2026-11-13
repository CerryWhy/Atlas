// Identificatori ontologici come branded type (SPEC §11): mai `string` nudo.
declare const brand: unique symbol;
type Brand<T, B extends string> = T & { readonly [brand]: B };

export type FmaId = Brand<string, "FmaId">;
export type MondoId = Brand<string, "MondoId">;
export type HpoId = Brand<string, "HpoId">;

const FMA_RE = /^FMA:\d+$/;
const MONDO_RE = /^MONDO:\d{7}$/;
const HPO_RE = /^HP:\d{7}$/;

export const isFmaId = (s: unknown): s is FmaId => typeof s === "string" && FMA_RE.test(s);
export const isMondoId = (s: unknown): s is MondoId => typeof s === "string" && MONDO_RE.test(s);
export const isHpoId = (s: unknown): s is HpoId => typeof s === "string" && HPO_RE.test(s);

export function asFmaId(s: string): FmaId {
  if (!isFmaId(s)) throw new Error(`FMA ID non valido: ${s}`);
  return s;
}

export function asMondoId(s: string): MondoId {
  if (!isMondoId(s)) throw new Error(`MONDO ID non valido: ${s}`);
  return s;
}
