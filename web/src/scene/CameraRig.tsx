import { useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { PerspectiveCamera, Vector3 } from "three";
import { useAtlasStore } from "../store/atlas";
import { prefersReducedMotion } from "./leader";

type OrbitLike = { target: Vector3; update: () => void };

/** Volo in corso: lo interrompe chi prende i comandi (vedi `cancelFlight`). */
const flight: { goal: { target: Vector3; position: Vector3 } | null } = { goal: null };

export function cancelFlight(): void {
  flight.goal = null;
}

/** Margine attorno alla sfera della struttura: 1 = la sfera tocca i bordi della vista. */
const MARGIN = 1.25;
const MIN_DISTANCE = 0.04;

/**
 * Distanza a cui una sfera di raggio `radius` entra tutta nella vista, sia in altezza
 * che in larghezza. Dal centroide, la camera resta fuori dalla sfera: nessuna
 * compenetrazione con la struttura inquadrata.
 */
export function fitDistance(radius: number, fovDeg: number, aspect: number): number {
  const vfov = (fovDeg * Math.PI) / 180;
  const hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);
  const half = Math.min(vfov, hfov) / 2;
  return Math.max((radius * MARGIN) / Math.sin(half), MIN_DISTANCE);
}

/**
 * flyTo(struttura): quando arriva la scheda di una struttura, la camera vola sul suo
 * centroide e si ferma alla distanza derivata dal suo raggio (structure.radius),
 * mantenendo l'angolo di vista corrente. Easing esponenziale: parte veloce, si posa.
 */
export function CameraRig() {
  // la scheda è un riferimento stabile: selezionarla non crea oggetti nuovi a ogni lettura
  const data = useAtlasStore((s) => (s.detail.state === "ok" ? s.detail.data : null));
  // senza una scheda aperta, la meta può venire dai risultati di "dal sintomo al corpo"
  const aim = useAtlasStore((s) => s.aim);
  const focus =
    data?.centroid && data.radius
      ? { id: data.fma_id, c: data.centroid, r: data.radius }
      : aim
        ? { id: `aim:${aim.id}`, c: aim.c, r: aim.r }
        : null;
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as OrbitLike | null;
  const size = useThree((s) => s.size);
  const last = useRef<string | null>(null);
  const dir = useMemo(() => new Vector3(), []);

  useFrame((_, dt) => {
    if (!controls) return;
    // nuova struttura: calcola la meta una volta sola
    if (focus && focus.id !== last.current) {
      last.current = focus.id;
      const target = new Vector3(...focus.c);
      dir.copy(camera.position).sub(controls.target);
      if (dir.lengthSq() < 1e-8) dir.set(0, 0, 1);
      dir.normalize();
      const fov = camera instanceof PerspectiveCamera ? camera.fov : 30;
      const distance = fitDistance(focus.r, fov, size.width / Math.max(size.height, 1));
      flight.goal = { target, position: target.clone().addScaledVector(dir, distance) };
    }
    if (!focus) last.current = null;

    const goal = flight.goal;
    if (!goal) return;
    const k = prefersReducedMotion() ? 1 : 1 - Math.exp(-dt * 4.5);
    controls.target.lerp(goal.target, k);
    camera.position.lerp(goal.position, k);
    controls.update();
    if (
      controls.target.distanceToSquared(goal.target) < 1e-8 &&
      camera.position.distanceToSquared(goal.position) < 1e-8
    ) {
      flight.goal = null;
    }
  });

  return null;
}
