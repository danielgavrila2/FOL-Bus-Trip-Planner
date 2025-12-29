import { useEffect, useState } from "react";
import { fetchRoutes, fetchRouteShape } from "../api/routes";
import { useMapStore } from "../store/mapStore";

export const RoutesPanel = () => {
  const [routes, setRoutes] = useState<any[]>([]);
  const { setSelectedRoute } = useMapStore();

  useEffect(() => {
    fetchRoutes().then(setRoutes);
  }, []);

  const selectRoute = async (route: any) => {
    const data = await fetchRouteShape(route.id);
    setSelectedRoute(data);
  };

  return (
    <div className="p-4">
      <h2 className="font-bold mb-2">Routes</h2>
      {routes.map(r => (
        <button
          key={r.id}
          className="block w-full text-left hover:bg-gray-200 dark:hover:bg-gray-700 p-2 rounded"
          onClick={() => selectRoute(r)}
        >
          {r.name}
        </button>
      ))}
    </div>
  );
};
