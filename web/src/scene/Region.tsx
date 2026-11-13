import { useGLTF } from "@react-three/drei";
import { useMemo } from "react";
import type { BufferGeometry, Mesh, Object3D } from "three";
import { meshUrl } from "../api/client";
import { useAtlasStore, type SceneNode } from "../store/atlas";
import { isFmaId } from "../types/ids";
import { Structure } from "./Structure";

const DRACO_DECODER = "/draco/";

type Part = { node: SceneNode; geometry: BufferGeometry };

const isMesh = (o: Object3D): o is Mesh => (o as Mesh).isMesh === true;

/**
 * Carica un GLB di regione e mappa ogni mesh al suo fma_id (I1).
 * L'ID arriva da `extras.fma_id` (→ userData): three.js sanifica i nomi dei nodi
 * e toglie i ':', quindi il nome del nodo non è affidabile lato client.
 */
export function Region({ file }: { file: string }) {
  const { scene } = useGLTF(meshUrl(file), DRACO_DECODER);
  const nodes = useAtlasStore((s) => s.nodes);

  const parts = useMemo<Part[]>(() => {
    scene.updateMatrixWorld(true);
    const out: Part[] = [];
    scene.traverse((o) => {
      if (!isMesh(o)) return;
      const id: unknown = o.userData.fma_id ?? o.parent?.userData.fma_id;
      const node = isFmaId(id) ? nodes.get(id) : undefined;
      if (!node) {
        console.warn(`[atlas] mesh senza struttura nota in ${file}: "${o.name}"`);
        return;
      }
      // Trasformazione cotta nella geometria: Bounds e raycast vedono coordinate di mondo.
      const geometry = o.geometry.clone().applyMatrix4(o.matrixWorld);
      if (!geometry.getAttribute("normal")) geometry.computeVertexNormals();
      out.push({ node, geometry });
    });
    return out;
  }, [scene, file, nodes]);

  return (
    <group>
      {parts.map((p) => (
        <Structure key={p.node.fma_id} {...p} />
      ))}
    </group>
  );
}
