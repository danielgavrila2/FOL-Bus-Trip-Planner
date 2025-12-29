import { MapContainer, TileLayer } from "react-leaflet";
import { PlanLayer } from "./PlanLayer";
import "leaflet/dist/leaflet.css";

export const TransitMap = () => (
  <MapContainer
    center={[46.7712, 23.6236]}
    zoom={13}
    className="h-full w-full"
  >
    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    <PlanLayer />
  </MapContainer>
);
