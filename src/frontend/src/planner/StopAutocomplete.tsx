import { useEffect, useState } from "react";
import { fetchStops } from "../api/stops";

export const StopAutocomplete = ({ onSelect }: any) => {
  const [stops, setStops] = useState<any[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetchStops().then(setStops);
  }, []);

  const filtered = stops.filter(s =>
    s.name.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="relative">
      <input
        className="w-full p-2 border rounded"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search stop"
      />
      {query && (
        <div className="absolute bg-white dark:bg-gray-800 shadow w-full max-h-48 overflow-auto">
          {filtered.map(s => (
            <div
              key={s.id}
              className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 cursor-pointer"
              onClick={() => {
                onSelect(s);
                setQuery(s.name);
              }}
            >
              {s.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
