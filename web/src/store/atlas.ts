import { create } from "zustand";
import type { FmaId } from "../types/ids";

type AtlasState = {
  selected: FmaId | null;
  hovered: FmaId | null;
  select: (id: FmaId | null) => void;
  hover: (id: FmaId | null) => void;
};

export const useAtlasStore = create<AtlasState>()((set) => ({
  selected: null,
  hovered: null,
  select: (selected) => set({ selected }),
  hover: (hovered) => set({ hovered }),
}));
