import {create} from "zustand";

export const usePlannerStore = create(set => ({
    result: null,
    saveProof: false,
    setResult: (r : any) => set({ result: r }),
    setSaveProof: (v: boolean) => set({ saveProof: v })
}));