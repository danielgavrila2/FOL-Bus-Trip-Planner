import { usePlannerStore } from "../store/plannerStore";

export const PlannerResults = () => {
  const result = usePlannerStore(s => s.result);
  if (!result) return null;

  return (
    <div className="mt-4 p-4 rounded bg-gray-100 dark:bg-gray-800">
      <p>⏱ {result.total_duration_minutes} min</p>
      <p>🎟 Tickets: {result.tickets_needed}</p>
      <p>💰 Cost: {result.total_cost}</p>
      <p>🧠 Proof: {result.proof_method}</p>

      {result.proof_files && (
        <div className="mt-2">
          {Object.values(result.proof_files).map((f: string) => (
            <a
              key={f}
              href={`http://localhost:8000/proof/${f}`}
              className="underline block"
            >
              Download {f}
            </a>
          ))}
        </div>
      )}
    </div>
  );
};
