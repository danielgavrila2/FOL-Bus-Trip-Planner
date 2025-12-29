import {api} from "./api";

export const fetchStops = async () => {
    const res = await api.get("/stops");
    return res.data.stops;
};