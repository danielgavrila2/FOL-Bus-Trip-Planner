import {create} from "zustand";

export const useCityStore = create(set => ({
    cityId: 2,
    setCity: (cityId: number) => set({ cityId })
}));