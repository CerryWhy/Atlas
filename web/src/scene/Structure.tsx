import { Outlines } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { Color, type BufferGeometry, type MeshPhysicalMaterial } from "three";
import { useAtlasStore, type SceneNode } from "../store/atlas";
import { prefersReducedMotion } from "./leader";
import { baseColor, DRAPE_SHADE, GROUPS, type Mode } from "./tissues";

type Props = { node: SceneNode; geometry: BufferGeometry };
type Look = { color: Color; emissive: Color; opacity: number };

const WHITE = new Color("#ffffff");
const BLACK = new Color("#000000");
const GHOST = new Color(GROUPS.frame.color);
const NO_RAYCAST = () => null;
/** Contorno della struttura attiva: tinta iodio dell'interfaccia, spessore in pixel. */
const OUTLINE_COLOR = "#e3a63f";
// In drei 9.122 il ramo `screenspace` del vertex shader è invertito: è con
// screenspace={false} che `thickness` si misura in pixel. Spessore fisso a ogni zoom.
const OUTLINE_PX = 2.5;

function lookOf(base: Color, s: { ghost: boolean; lit: boolean; dim: boolean; hot: boolean }): Look {
  if (s.ghost) return { color: GHOST, emissive: BLACK, opacity: s.dim ? 0.04 : 0.1 };
  if (s.lit) {
    return {
      color: base.clone().lerp(WHITE, 0.1),
      emissive: base.clone().multiplyScalar(0.3),
      opacity: 1,
    };
  }
  // Con una selezione attiva il resto diventa una radiografia: velato, ma ancora cliccabile.
  if (s.dim) {
    return {
      color: base.clone().lerp(DRAPE_SHADE, s.hot ? 0.15 : 0.5),
      emissive: BLACK,
      opacity: s.hot ? 0.5 : 0.2,
    };
  }
  if (s.hot) {
    return {
      color: base.clone().lerp(WHITE, 0.16),
      emissive: base.clone().multiplyScalar(0.12),
      opacity: 1,
    };
  }
  return { color: base, emissive: BLACK, opacity: 1 };
}

/** Una mesh anatomica: tinta del tessuto, hover, selezione, modalità di gruppo. */
export function Structure({ node, geometry }: Props) {
  const mode = useAtlasStore((s) => s.modes[node.group]);
  const lit = useAtlasStore((s) => s.lit.has(node.fma_id));
  const anySelected = useAtlasStore((s) => s.selected !== null);
  const hot = useAtlasStore((s) => s.hoveredFocus === node.focus_fma_id);
  const select = useAtlasStore((s) => s.select);
  const hover = useAtlasStore((s) => s.hover);
  const isolated = useAtlasStore((s) => s.isolated);

  // Una struttura selezionata si mostra piena anche se il suo gruppo è spento;
  // in isolamento tutto il resto sparisce.
  const effective: Mode = lit ? "solid" : isolated && anySelected ? "hidden" : mode;
  const ghost = effective === "ghost";

  const dim = anySelected && !lit;
  // Materiale trasparente (senza scrittura di profondità) per i veli e per la radiografia.
  const sheer = ghost || dim;

  const base = useMemo(() => baseColor(node.group, node.focus_fma_id), [node]);
  const look = useMemo(() => lookOf(base, { ghost, lit, dim, hot }), [base, ghost, lit, dim, hot]);

  // Ciò che è a schermo in questo momento: il materiale nuovo riparte da qui,
  // così il passaggio pieno ↔ velato è una dissolvenza e non uno scatto.
  const shown = useRef<Look | null>(null);
  const initial = useMemo(
    () => {
      const from = shown.current ?? look;
      return { color: from.color.clone(), emissive: from.emissive.clone(), opacity: from.opacity };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sheer],
  );

  const material = useRef<MeshPhysicalMaterial>(null);
  useFrame((_, dt) => {
    const m = material.current;
    if (!m) return;
    const k = prefersReducedMotion() ? 1 : 1 - Math.exp(-dt * 14);
    m.color.lerp(look.color, k);
    m.emissive.lerp(look.emissive, k);
    m.opacity += (look.opacity - m.opacity) * k;
    const now = (shown.current ??= { color: new Color(), emissive: new Color(), opacity: 1 });
    now.color.copy(m.color);
    now.emissive.copy(m.emissive);
    now.opacity = m.opacity;
  });

  if (effective === "hidden") return null;

  const onOver = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    hover(node.fma_id);
    document.body.style.cursor = "pointer";
  };
  const onOut = () => {
    hover(null);
    document.body.style.cursor = "";
  };
  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    select(node.focus_fma_id);
  };

  return (
    <mesh
      name={node.fma_id}
      userData={{ fma_id: node.fma_id }}
      geometry={geometry}
      renderOrder={ghost ? 3 : dim ? 2 : 1}
      raycast={ghost ? NO_RAYCAST : undefined}
      onPointerOver={ghost ? undefined : onOver}
      onPointerOut={ghost ? undefined : onOut}
      onClick={ghost ? undefined : onClick}
    >
      <meshPhysicalMaterial
        key={sheer ? "sheer" : "solid"}
        ref={material}
        args={[initial]}
        transparent={sheer}
        depthWrite={!sheer}
        roughness={ghost ? 0.35 : 0.56}
        metalness={0}
        clearcoat={sheer ? 0 : 0.35}
        clearcoatRoughness={0.5}
      />
      {lit && !sheer && (
        <Outlines color={OUTLINE_COLOR} thickness={OUTLINE_PX} screenspace={false} />
      )}
    </mesh>
  );
}
