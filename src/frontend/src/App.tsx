import { TransitMap } from "./map/TransitMap";
import { PlannerPanel } from "./planner/PlannerPanel";

export default function App() {
  return (
    <div className="flex h-full">
      <div className="w-96">
        <PlannerPanel />
      </div>
      <TransitMap />
    </div>
  );
}
