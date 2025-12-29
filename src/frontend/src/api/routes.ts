import { api } from "./api";

export const fetchRoutes = async () => {
  const res = await api.get("/routes");
  return res.data.routes;
};

export const fetchRouteShape = async (routeId: string) => {
  // you already said this is available via Tranzy
  const res = await api.get(`/routes/${routeId}/shape`);
  return res.data;
};
