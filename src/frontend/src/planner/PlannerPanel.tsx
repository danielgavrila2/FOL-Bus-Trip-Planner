import { api } from "../api/api";
import { usePlannerStore } from "../store/plannerStore";
import { useState } from "react";

export const PlannerPanel = () => {
  const { setResult, saveProof, setSaveProof } = usePlannerStore();
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const plan = async () => {
    const res = await api.post("/plan", {
      start_stop: start,
      end_stop: end,
      save_input: saveProof
    });
    setResult(res.data);
  };

  return (
    <div className="p-4 bg-white dark:bg-gray-900">
      <input placeholder="Start stop" onChange={e => setStart(e.target.value)} />
      <input placeholder="End stop" onChange={e => setEnd(e.target.value)} />
      <label>
        <input
          type="checkbox"
          checked={saveProof}
          onChange={e => setSaveProof(e.target.checked)}
        />
        Save proof
      </label>
      <button onClick={plan}>Plan</button>
    </div>
  );
};
