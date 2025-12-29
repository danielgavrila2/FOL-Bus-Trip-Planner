import { create } from "zustand";

export const useMapStore = create(set => ({
  mode: "plan", // "plan" | "route"
  selectedRoute: null,
  setMode: (mode: "plan" | "route") => set({ mode }),
  setSelectedRoute: (route: any) => set({ selectedRoute: route })
}));
