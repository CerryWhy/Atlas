import type { components } from "../types/atlas";
import { asFmaId, type FmaId } from "../types/ids";

type Schemas = components["schemas"];
export type Citation = Schemas["Citation"];
export type SourceRelease = Schemas["SourceRelease"];
export type MeshFile = Schemas["MeshFile"];
export type Disease = Schemas["Disease"];
export type Phenotype = Schemas["Phenotype"];
export type InheritedLink = Schemas["InheritedLink"];
export type LocatedPhenotype = Schemas["LocatedPhenotype"];
export type LocatedStructure = Omit<Schemas["LocatedStructure"], "fma_id" | "mesh_nodes"> & {
  fma_id: FmaId;
  mesh_nodes: FmaId[];
};
export type Located = { phenotypes: LocatedPhenotype[]; structures: LocatedStructure[] };
export type StructureRef = Omit<Schemas["StructureRef"], "fma_id"> & { fma_id: FmaId };
export type ChildRef = Omit<Schemas["ChildRef"], "fma_id"> & { fma_id: FmaId };
export type MeshNode = Omit<Schemas["MeshNode"], "fma_id" | "focus_fma_id"> & {
  fma_id: FmaId;
  focus_fma_id: FmaId;
};
export type Structure = Omit<
  Schemas["Structure"],
  "fma_id" | "ancestors" | "children" | "mesh_nodes"
> & {
  fma_id: FmaId;
  ancestors: StructureRef[];
  children: ChildRef[];
  mesh_nodes: FmaId[];
};

const BASE = "/api";
const API_KEY = import.meta.env.VITE_ATLAS_API_KEY as string | undefined;

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(BASE + path, {
    signal,
    headers: API_KEY ? { "X-API-Key": API_KEY } : {},
  });
  if (!res.ok) throw new Error(`Il server ha risposto ${res.status} a ${path}`);
  return (await res.json()) as T;
}

const branded = <T extends { fma_id: string }>(x: T): Omit<T, "fma_id"> & { fma_id: FmaId } => ({
  ...x,
  fma_id: asFmaId(x.fma_id),
});

export async function getStructure(id: FmaId, signal?: AbortSignal): Promise<Structure> {
  const raw = await get<Schemas["Structure"]>(`/structure/${encodeURIComponent(id)}`, signal);
  return {
    ...raw,
    fma_id: asFmaId(raw.fma_id),
    ancestors: raw.ancestors.map(branded),
    children: raw.children.map(branded),
    mesh_nodes: raw.mesh_nodes.map(asFmaId),
  };
}

/** Dal sintomo al corpo (Fase 5). Il testo non viene salvato dal server. */
export async function postLocate(text: string, signal?: AbortSignal): Promise<Located> {
  const res = await fetch(BASE + "/locate", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", ...(API_KEY ? { "X-API-Key": API_KEY } : {}) },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`Il server ha risposto ${res.status} a /locate`);
  const raw = (await res.json()) as Schemas["Located"];
  return {
    phenotypes: raw.phenotypes,
    structures: raw.structures.map((s) => ({
      ...s,
      fma_id: asFmaId(s.fma_id),
      mesh_nodes: s.mesh_nodes.map(asFmaId),
    })),
  };
}

export function getRegions(signal?: AbortSignal): Promise<MeshFile[]> {
  return get<MeshFile[]>("/regions", signal);
}

export async function getRegionNodes(file: string, signal?: AbortSignal): Promise<MeshNode[]> {
  const raw = await get<Schemas["MeshNode"][]>(
    `/regions/${encodeURIComponent(file)}/nodes`,
    signal,
  );
  return raw.map((n) => ({
    ...n,
    fma_id: asFmaId(n.fma_id),
    focus_fma_id: asFmaId(n.focus_fma_id),
  }));
}

export function getAttribution(signal?: AbortSignal): Promise<SourceRelease[]> {
  return get<SourceRelease[]>("/attribution", signal);
}

export const meshUrl = (file: string): string => `/meshes/${encodeURIComponent(file)}`;
