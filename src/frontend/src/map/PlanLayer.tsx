import { Polyline } from "react-leaflet";
import { usePlannerStore } from "../store/plannerStore";

export const PlanLayer = () => {
  const result = usePlannerStore(s => s.result);
  if (!result) return null;

  return (
    <>
      {result.route.map((seg: any, i: number) => (
        <Polyline
          key={i}
          positions={seg.shape || []}
          color={["blue", "red", "green"][i % 3]}
          weight={6}
        />
      ))}
    </>
  );
};
