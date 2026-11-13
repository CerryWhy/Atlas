import { Bounds, OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import type { MeshFile } from "../api/client";
import { useAtlasStore } from "../store/atlas";
import { Region } from "./Region";

/** <Canvas>, luci, controlli. Le regioni arrivano dall'API, nessun GLB cablato. */
export function Atlas({ regions }: { regions: MeshFile[] }) {
  const select = useAtlasStore((s) => s.select);

  return (
    <Canvas
      camera={{ fov: 35, near: 0.01, far: 50, position: [0, 1.2, 1.2] }}
      onPointerMissed={() => select(null)}
      dpr={[1, 2]}
    >
      <color attach="background" args={["#0f1115"]} />
      <hemisphereLight args={["#ffffff", "#2a2a35", 0.9]} />
      <directionalLight position={[1, 2, 2]} intensity={1.6} />
      <directionalLight position={[-2, 0.5, -1]} intensity={0.5} />
      {/* I controlli devono esistere prima di Bounds, che ne sposta il target. */}
      <OrbitControls makeDefault enableDamping />
      <Suspense fallback={null}>
        <Bounds fit clip observe margin={1.3}>
          {regions.map((r) => (
            <Region key={r.mesh_file} file={r.mesh_file} />
          ))}
        </Bounds>
      </Suspense>
    </Canvas>
  );
}
