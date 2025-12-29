import React, { createContext, useContext, useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix Leaflet default marker icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// ============= TYPES =============
interface Stop {
  id: string;
  name: string;
  lat: number;
  lon: number;
}

interface Route {
  id: string;
  name: string;
  long_name: string;
}

interface RouteShape {
  route_id: string;
  route_name: string;
  direction: number;
  pattern: string;
  shape: Array<{ lat: number; lon: number; seq: number }>;
  stops: Array<{ id: string; name: string; lat: number; lon: number }>;
}

interface RouteSegment {
  from_stop: string;
  to_stop: string;
  route_name: string;
  route_id: string;
  duration_minutes: number;
}

interface TripResponse {
  success: boolean;
  route: RouteSegment[];
  total_duration_minutes: number;
  total_transfers: number;
  total_cost: number;
  tickets_needed: number;
  proof_method: string;
  error?: string;
}

// ============= CONSTANTS =============
const API_BASE = 'http://localhost:8000';
const CITIES = {
  'cluj-napoca': { name: 'Cluj-Napoca', center: [46.7712, 23.6236] as [number, number], zoom: 13 }
};

const ROUTE_COLORS = ['#2563eb', '#16a34a', '#dc2626', '#7c3aed', '#ea580c', '#0891b2'];

// ============= I18N =============
const translations = {
  en: {
    'app.title': 'Transit Planner',
    'planner.start': 'Start stop',
    'planner.end': 'End stop',
    'planner.plan': 'Plan trip',
    'planner.duration': 'Duration',
    'planner.transfers': 'Transfers',
    'planner.tickets': 'Tickets required',
    'planner.cost': 'Total cost',
    'planner.proof': 'Proof method',
    'planner.fewer': 'Prefer fewer transfers',
    'planner.save': 'Save proof input',
    'planner.direct': 'Include direct routes',
    'planner.loading': 'Planning...',
    'planner.error': 'Error',
    'planner.select': 'Select a stop',
    'planner.route': 'Route',
    'map.selectRoute': 'Select a route to view',
    'map.loading': 'Loading map data...'
  },
  ro: {
    'app.title': 'Planificator Transport',
    'planner.start': 'Stație plecare',
    'planner.end': 'Stație sosire',
    'planner.plan': 'Planifică ruta',
    'planner.duration': 'Durată',
    'planner.transfers': 'Transferuri',
    'planner.tickets': 'Bilete necesare',
    'planner.cost': 'Cost total',
    'planner.proof': 'Metodă de demonstrație',
    'planner.fewer': 'Preferă mai puține transferuri',
    'planner.save': 'Salvează input demonstrație',
    'planner.direct': 'Include rute directe',
    'planner.loading': 'Se planifică...',
    'planner.error': 'Eroare',
    'planner.select': 'Selectează o stație',
    'planner.route': 'Ruta',
    'map.selectRoute': 'Selectează o rută pentru vizualizare',
    'map.loading': 'Se încarcă harta...'
  }
};

// ============= CONTEXTS =============
const ThemeContext = createContext<{
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}>({ theme: 'light', toggleTheme: () => {} });

const LanguageContext = createContext<{
  lang: 'en' | 'ro';
  setLang: (l: 'en' | 'ro') => void;
  t: (key: string) => string;
}>({ lang: 'en', setLang: () => {}, t: (k) => k });

const AppContext = createContext<{
  city: keyof typeof CITIES;
  stops: Stop[];
  routes: Route[];
  selectedRoute: RouteShape | null;
  setSelectedRoute: (r: RouteShape | null) => void;
  tripResult: TripResponse | null;
  setTripResult: (r: TripResponse | null) => void;
}>({
  city: 'cluj-napoca',
  stops: [],
  routes: [],
  selectedRoute: null,
  setSelectedRoute: () => {},
  tripResult: null,
  setTripResult: () => {}
});

// ============= API =============
const api = {
  async getStops(): Promise<Stop[]> {
    const res = await fetch(`${API_BASE}/stops`);
    const data = await res.json();
    return data.stops;
  },
  
  async getRoutes(): Promise<Route[]> {
    const res = await fetch(`${API_BASE}/routes`);
    const data = await res.json();
    return data.routes;
  },
  
  async getRouteShape(routeId: string, direction: number = 0): Promise<RouteShape> {
    const res = await fetch(`${API_BASE}/routes/${routeId}/shape?direction=${direction}`);
    return await res.json();
  },
  
  async planTrip(
    startStop: string,
    endStop: string,
    preferFewer: boolean,
    saveInput: boolean,
    includeDirect: boolean
  ): Promise<TripResponse> {
    const res = await fetch(`${API_BASE}/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_stop: startStop,
        end_stop: endStop,
        prefer_fewer_transfers: preferFewer,
        save_input: saveInput,
        include_direct_routes: includeDirect
      })
    });
    return await res.json();
  }
};

// ============= COMPONENTS =============

// Header
function Header() {
  const { theme, toggleTheme } = useContext(ThemeContext);
  const { lang, setLang, t } = useContext(LanguageContext);

  return (
    <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">
          {t('app.title')}
        </h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setLang(lang === 'en' ? 'ro' : 'en')}
            className="px-3 py-1 text-sm font-medium rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            {lang === 'en' ? 'RO' : 'EN'}
          </button>
          <button
            onClick={toggleTheme}
            className="p-2 rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            {theme === 'light' ? '🌙' : '☀️'}
          </button>
        </div>
      </div>
    </header>
  );
}

// Route Selector
function RouteSelector() {
  const { routes, setSelectedRoute } = useContext(AppContext);
  const { t } = useContext(LanguageContext);
  const [loading, setLoading] = useState(false);

  const handleSelect = async (routeId: string) => {
    if (!routeId) {
      setSelectedRoute(null);
      return;
    }
    
    setLoading(true);
    try {
      const shape = await api.getRouteShape(routeId);
      setSelectedRoute(shape);
    } catch (err) {
      console.error('Failed to load route shape:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        {t('map.selectRoute')}
      </label>
      <select
        onChange={(e) => handleSelect(e.target.value)}
        disabled={loading}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
      >
        <option value="">{t('planner.select')}</option>
        {routes.map(r => (
          <option key={r.id} value={r.id}>
            {r.name} - {r.long_name}
          </option>
        ))}
      </select>
    </div>
  );
}

// Planner Form
function PlannerForm() {
  const { stops, setTripResult } = useContext(AppContext);
  const { t } = useContext(LanguageContext);
  const [startStop, setStartStop] = useState('');
  const [endStop, setEndStop] = useState('');
  const [preferFewer, setPreferFewer] = useState(true);
  const [saveInput, setSaveInput] = useState(false);
  const [includeDirect, setIncludeDirect] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!startStop || !endStop) return;

    setLoading(true);
    setError('');
    setTripResult(null);

    try {
      const result = await api.planTrip(startStop, endStop, preferFewer, saveInput, includeDirect);
      setTripResult(result);
      if (!result.success && result.error) {
        setError(result.error);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to plan trip');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('planner.start')}
        </label>
        <select
          value={startStop}
          onChange={(e) => setStartStop(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          required
        >
          <option value="">{t('planner.select')}</option>
          {stops.map(s => (
            <option key={s.id} value={s.name}>{s.name}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {t('planner.end')}
        </label>
        <select
          value={endStop}
          onChange={(e) => setEndStop(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          required
        >
          <option value="">{t('planner.select')}</option>
          {stops.map(s => (
            <option key={s.id} value={s.name}>{s.name}</option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={preferFewer}
            onChange={(e) => setPreferFewer(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-gray-700 dark:text-gray-300">{t('planner.fewer')}</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={saveInput}
            onChange={(e) => setSaveInput(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-gray-700 dark:text-gray-300">{t('planner.save')}</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={includeDirect}
            onChange={(e) => setIncludeDirect(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-gray-700 dark:text-gray-300">{t('planner.direct')}</span>
        </label>
      </div>

      {error && (
        <div className="p-3 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 rounded text-sm">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium rounded"
      >
        {loading ? t('planner.loading') : t('planner.plan')}
      </button>
    </form>
  );
}

// Trip Results
function TripResults() {
  const { tripResult } = useContext(AppContext);
  const { t } = useContext(LanguageContext);

  if (!tripResult || !tripResult.success) return null;

  return (
    <div className="mt-6 space-y-4">
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded">
          <div className="text-gray-600 dark:text-gray-400">{t('planner.duration')}</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">
            {tripResult.total_duration_minutes} min
          </div>
        </div>
        <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded">
          <div className="text-gray-600 dark:text-gray-400">{t('planner.transfers')}</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">
            {tripResult.total_transfers}
          </div>
        </div>
        <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded">
          <div className="text-gray-600 dark:text-gray-400">{t('planner.tickets')}</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">
            {tripResult.tickets_needed}
          </div>
        </div>
        <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded">
          <div className="text-gray-600 dark:text-gray-400">{t('planner.cost')}</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">
            {tripResult.total_cost.toFixed(2)} RON
          </div>
        </div>
      </div>

      <div className="p-3 bg-blue-50 dark:bg-blue-900 rounded">
        <div className="text-xs text-blue-600 dark:text-blue-300 mb-1">{t('planner.proof')}</div>
        <div className="text-sm text-blue-900 dark:text-blue-100 font-mono">
          {tripResult.proof_method}
        </div>
      </div>

      <div className="space-y-2">
        {tripResult.route.map((seg, i) => (
          <div
            key={i}
            className="p-3 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs font-semibold rounded">
                {seg.route_name}
              </span>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {seg.duration_minutes} min
              </span>
            </div>
            <div className="text-sm text-gray-900 dark:text-white">
              {seg.from_stop} → {seg.to_stop}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Map Layer: Route Shape
function RouteLayer() {
  const { selectedRoute } = useContext(AppContext);

  if (!selectedRoute || !selectedRoute.shape.length) return null;

  const positions: [number, number][] = selectedRoute.shape.map(p => [p.lat, p.lon]);

  return (
    <>
      <Polyline positions={positions} color="#2563eb" weight={4} opacity={0.7} />
      {selectedRoute.stops.map(stop => (
        <Marker key={stop.id} position={[stop.lat, stop.lon]}>
          <Popup>{stop.name}</Popup>
        </Marker>
      ))}
    </>
  );
}

// Map Layer: Planned Path
function PlannedPathLayer() {
  const { tripResult, stops } = useContext(AppContext);

  if (!tripResult || !tripResult.success) return null;

  const segments = tripResult.route.map((seg, i) => {
    const fromStop = stops.find(s => s.name === seg.from_stop);
    const toStop = stops.find(s => s.name === seg.to_stop);
    
    if (!fromStop || !toStop) return null;

    const color = ROUTE_COLORS[i % ROUTE_COLORS.length];
    return {
      positions: [[fromStop.lat, fromStop.lon], [toStop.lat, toStop.lon]] as [number, number][],
      color
    };
  }).filter(Boolean);

  return (
    <>
      {segments.map((seg, i) => seg && (
        <Polyline key={i} positions={seg.positions} color={seg.color} weight={5} opacity={0.8} />
      ))}
    </>
  );
}

// Map component
function TransitMap() {
  const { city } = useContext(AppContext);
  const cityData = CITIES[city];

  return (
    <MapContainer
      center={cityData.center}
      zoom={cityData.zoom}
      scrollWheelZoom
      className="h-full w-full"
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      <RouteLayer />
      <PlannedPathLayer />
    </MapContainer>
  );
}

// Main App
function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [lang, setLang] = useState<'en' | 'ro'>('en');
  const [stops, setStops] = useState<Stop[]>([]);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<RouteShape | null>(null);
  const [tripResult, setTripResult] = useState<TripResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  useEffect(() => {
    Promise.all([api.getStops(), api.getRoutes()])
      .then(([s, r]) => {
        setStops(s);
        setRoutes(r);
      })
      .catch(err => console.error('Failed to load data:', err))
      .finally(() => setLoading(false));
  }, []);

  const t = (key: string) => translations[lang][key] || key;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-gray-600 dark:text-gray-400">{t('map.loading')}</div>
      </div>
    );
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme: () => setTheme(t => t === 'light' ? 'dark' : 'light') }}>
      <LanguageContext.Provider value={{ lang, setLang, t }}>
        <AppContext.Provider value={{
          city: 'cluj-napoca',
          stops,
          routes,
          selectedRoute,
          setSelectedRoute,
          tripResult,
          setTripResult
        }}>
          <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
            <Header />
            <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
              <aside className="w-full lg:w-96 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 p-4 overflow-y-auto">
                <RouteSelector />
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    {t('planner.plan')}
                  </h2>
                  <PlannerForm />
                  <TripResults />
                </div>
              </aside>
              <main className="flex-1 h-96 lg:h-auto">
                <TransitMap />
              </main>
            </div>
          </div>
        </AppContext.Provider>
      </LanguageContext.Provider>
    </ThemeContext.Provider>
  );
}

export default App;