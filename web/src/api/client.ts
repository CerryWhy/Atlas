import type { components } from "../types/atlas";
import { asFmaId, asMondoId, type FmaId, type MondoId } from "../types/ids";

type Schemas = components["schemas"];
export type Citation = Schemas["Citation"];
export type SourceRelease = Schemas["SourceRelease"];
export type Disease = Omit<Schemas["Disease"], "mondo_id"> & { mondo_id: MondoId };
export type Structure = Omit<Schemas["Structure"], "fma_id" | "diseases"> & {
  fma_id: FmaId;
  diseases: Disease[];
};

const BASE = "/api";
const API_KEY = import.meta.env.VITE_ATLAS_API_KEY as string | undefined;

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(BASE + path, {
    signal,
    headers: API_KEY ? { "X-API-Key": API_KEY } : {},
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return (await res.json()) as T;
}

export async function getStructure(id: FmaId, signal?: AbortSignal): Promise<Structure> {
  const raw = await get<Schemas["Structure"]>(`/structure/${encodeURIComponent(id)}`, signal);
  return {
    ...raw,
    fma_id: asFmaId(raw.fma_id),
    diseases: raw.diseases.map((d) => ({ ...d, mondo_id: asMondoId(d.mondo_id) })),
  };
}

export type MeshFile = Schemas["MeshFile"];

export function getRegions(signal?: AbortSignal): Promise<MeshFile[]> {
  return get<MeshFile[]>("/regions", signal);
}

export function getAttribution(signal?: AbortSignal): Promise<SourceRelease[]> {
  return get<SourceRelease[]>("/attribution", signal);
}

export const meshUrl = (file: string): string => `/meshes/${encodeURIComponent(file)}`;
