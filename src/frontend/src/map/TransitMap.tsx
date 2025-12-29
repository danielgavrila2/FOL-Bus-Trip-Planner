import { MapContainer, TileLayer } from "react-leaflet";
import { PlanLayer } from "./PlanLayer";
import { RouteLayer } from "./RouteLayer";
import { useMapStore } from "../store/mapStore";

export const TransitMap = () => {
  const mode = useMapStore(s => s.mode);

  return (
    <MapContainer center={[46.7712, 23.6236]} zoom={13} className="h-full w-full">
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {mode === "plan" && <PlanLayer />}
      {mode === "route" && <RouteLayer />}
    </MapContainer>
  );
};
