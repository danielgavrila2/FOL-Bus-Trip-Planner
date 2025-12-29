import { Polyline, Marker } from "react-leaflet";
import { useMapStore } from "../store/mapStore";

export const RouteLayer = () => {
  const route = useMapStore(s => s.selectedRoute);
  if (!route) return null;

  return (
    <>
      <Polyline
        positions={route.shape.map((p: any) => [p.lat, p.lon])}
        color="#2563eb"
        weight={6}
      />
      {route.stops.map((s: any) => (
        <Marker key={s.id} position={[s.lat, s.lon]} />
      ))}
    </>
  );
};
