import { Bounds, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useMemo } from "react";
import { Vector3 } from "three";
import { useAtlasStore } from "../store/atlas";
import { leaderBus } from "./leader";
import { Region } from "./Region";

/** Proietta sullo schermo il centroide della struttura selezionata, a ogni frame. */
function LeaderProbe() {
  const centroid = useAtlasStore((s) => (s.detail.state === "ok" ? s.detail.data.centroid : null));
  const v = useMemo(() => new Vector3(), []);

  useFrame(({ camera, size }) => {
    if (!centroid) {
      leaderBus.publish(null);
      return;
    }
    v.set(centroid[0], centroid[1], centroid[2]).project(camera);
    const behind = v.z > 1;
    leaderBus.publish(
      behind ? null : { x: (v.x * 0.5 + 0.5) * size.width, y: (-v.y * 0.5 + 0.5) * size.height },
    );
  });
  return null;
}

/** <Canvas>, luci, controlli. Le regioni arrivano dall'API: nessun GLB cablato. */
export function Atlas() {
  const regions = useAtlasStore((s) => s.regions);
  const select = useAtlasStore((s) => s.select);

  return (
    <Canvas
      camera={{ fov: 30, near: 0.01, far: 50, position: [0, 1.0, 1.6] }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
      onPointerMissed={() => select(null)}
    >
      {/* Luce da sala: chiave calda dall'alto, controluce freddo che stacca dal telo. */}
      <hemisphereLight args={["#f6fffa", "#12302d", 0.8]} />
      <directionalLight position={[1.2, 2.4, 2.6]} intensity={2.2} color="#fff4e6" />
      <directionalLight position={[-2.6, 0.9, -1.4]} intensity={1.1} color="#bfe6da" />
      {/* I controlli devono esistere prima di Bounds, che ne sposta il target. */}
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        minDistance={0.2}
        maxDistance={3}
      />
      <Suspense fallback={null}>
        <Bounds fit clip observe margin={1.05}>
          {regions.map((r) => (
            <Region key={r.mesh_file} file={r.mesh_file} />
          ))}
        </Bounds>
      </Suspense>
      <LeaderProbe />
    </Canvas>
  );
}
