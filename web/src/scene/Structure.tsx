import type { ThreeEvent } from "@react-three/fiber";
import type { BufferGeometry } from "three";
import { useAtlasStore } from "../store/atlas";
import type { FmaId } from "../types/ids";

const COLOR = { base: "#9a5544", hover: "#b86f58", selected: "#e08a5e" } as const;

type Props = { fmaId: FmaId; geometry: BufferGeometry };

/** Una mesh anatomica: hover, selezione, evidenziazione. */
export function Structure({ fmaId, geometry }: Props) {
  const isSelected = useAtlasStore((s) => s.selected === fmaId);
  const isHovered = useAtlasStore((s) => s.hovered === fmaId);
  const select = useAtlasStore((s) => s.select);
  const hover = useAtlasStore((s) => s.hover);

  const onOver = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    hover(fmaId);
    document.body.style.cursor = "pointer";
  };
  const onOut = () => {
    hover(null);
    document.body.style.cursor = "";
  };
  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    select(fmaId);
  };

  const color = isSelected ? COLOR.selected : isHovered ? COLOR.hover : COLOR.base;

  return (
    <mesh
      name={fmaId}
      userData={{ fma_id: fmaId }}
      geometry={geometry}
      onPointerOver={onOver}
      onPointerOut={onOut}
      onClick={onClick}
    >
      <meshStandardMaterial
        color={color}
        roughness={0.55}
        metalness={0.05}
        emissive={isSelected ? "#3a1408" : "#000000"}
      />
    </mesh>
  );
}
