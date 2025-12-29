import { api } from "./api";

export const fetchRoutes = async () => {
  const res = await api.get("/routes");
  return res.data.routes;
};

export const fetchRouteShape = async (routeId: string) => {
  const res = await api.get(`/routes/${routeId}/shape`);
  return res.data;
};
