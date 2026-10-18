import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import Plot from "react-plotly.js";

const API = import.meta.env.VITE_API_URL ?? "/api";
const HYPOXIA_LIMIT = 3.5;
const LETHAL_LIMIT = 2.0;
const OPTIMIZER_COUNTS = [10000, 20000, 30000, 40000, 50000];
const FONT = '"Schibsted Grotesk", system-ui, sans-serif';
const PLOT_CONFIG = { responsive: true, displaylogo: false };

type Tab = "spatial" | "diurnal" | "feasibility" | "optimizer" | "report";
type PlotFigure = { data: any[]; layout?: Record<string, any>; frames?: any[] };

type Config = {
  length: number; width: number; depth: number; grid: string; stocking_count: number;
  individual_weight_g: number; feed_type: string; aeration_enabled: boolean;
  aeration_start_hour: number; aeration_end_hour: number;
};

type FormState = Config & {
  source: string; latitude: number; longitude: number; location_name: string;
  weather_condition: string;
};

const initialForm: FormState = {
  source: "synthetic", latitude: 14.7565, longitude: 121.0441,
  location_name: "Caloocan City, Metro Manila", weather_condition: "Sunny / Clear Skies",
  length: 20, width: 20, depth: 1.5, grid: "fast", stocking_count: 18000,
  individual_weight_g: 18, feed_type: "Ordinary Commercial Feed", aeration_enabled: false,
  aeration_start_hour: 1, aeration_end_hour: 6,
};

const TABS: { key: Tab; label: string }[] = [
  { key: "spatial", label: "Spatial field" },
  { key: "diurnal", label: "24-hour dynamics" },
  { key: "feasibility", label: "Feasibility" },
  { key: "optimizer", label: "Scenario optimizer" },
  { key: "report", label: "Research report" },
];

const FEEDS = [
  { value: "Ordinary Commercial Feed", title: "Ordinary commercial feed", sub: "34% protein, lower cost" },
  { value: "Fortified Growth-Booster Feed", title: "Fortified growth-booster feed", sub: "42% protein, faster growth, higher oxygen demand" },
];

/* ---------- validation (mirrors the limits in backend/main.py) ---------- */

const LIMITS: Partial<Record<keyof FormState, [number, number, string]>> = {
  length: [10, 100, "m"], width: [10, 100, "m"], depth: [0.8, 3, "m"],
  stocking_count: [1000, 200000, ""], individual_weight_g: [5, 35, "g"],
  latitude: [-90, 90, "°"], longitude: [-180, 180, "°"],
  aeration_start_hour: [0, 23, ""], aeration_end_hour: [0, 23, ""],
};
const INTEGER_KEYS: (keyof FormState)[] = ["stocking_count", "aeration_start_hour", "aeration_end_hour"];
type FormErrors = Partial<Record<keyof FormState, string>>;

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {};
  (Object.keys(LIMITS) as (keyof FormState)[]).forEach((key) => {
    if ((key === "latitude" || key === "longitude") && form.source !== "live") return;
    if ((key === "aeration_start_hour" || key === "aeration_end_hour") && !form.aeration_enabled) return;
    const [min, max, unit] = LIMITS[key]!;
    const value = form[key] as number;
    if (!Number.isFinite(value)) errors[key] = "Enter a number";
    else if (INTEGER_KEYS.includes(key) && !Number.isInteger(value)) errors[key] = "Use a whole number";
    else if (value < min || value > max) errors[key] = `Use ${min} to ${max}${unit ? ` ${unit}` : ""}`;
  });
  if (
    form.aeration_enabled && !errors.aeration_start_hour && !errors.aeration_end_hour &&
    form.aeration_start_hour > form.aeration_end_hour
  ) {
    errors.aeration_end_hour = "End must be at or after start";
  }
  return errors;
}

/* ---------- helpers ---------- */

const pad = (value: number) => String(value).padStart(2, "0");
const sentence = (value: string) => value.charAt(0) + value.slice(1).toLowerCase();
const verdictTone = (verdict: string): "success" | "warning" | "danger" =>
  verdict === "FEASIBLE" ? "success" : verdict === "NOT FEASIBLE" ? "danger" : "warning";
const isAbort = (problem: unknown) => problem instanceof DOMException && problem.name === "AbortError";

function describe(problem: unknown, fallback: string) {
  if (problem instanceof TypeError) return "Can't reach the EcoPrawn API. Check that the backend is running on port 8000.";
  return problem instanceof Error ? problem.message : fallback;
}

async function errorMessage(response: Response, fallback?: string) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: any) => `${(item.loc ?? []).slice(1).join(".")} ${item.msg}`.trim()).join("; ");
    }
  } catch {
    /* body was not JSON */
  }
  return fallback ?? `Request failed (${response.status})`;
}

async function getJson(url: string, signal?: AbortSignal) {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

const reportCache = new Map<string, string>();

/* ---------- icons ---------- */

const ICONS: Record<string, ReactNode> = {
  sliders: <><path d="M4 7h9M17 7h3M4 17h3M11 17h9" /><circle cx="15" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></>,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  play: <path d="M8 5l11 7-11 7z" fill="currentColor" />,
  pause: <path d="M8 5v14M16 5v14" strokeWidth="2.6" />,
  check: <><circle cx="12" cy="12" r="9" /><path d="M8 12.5l2.7 2.7L16 9.5" /></>,
  alert: <><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17.2v.1" /></>,
  cross: <><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></>,
  download: <path d="M12 4v11M7.5 10.5L12 15l4.5-4.5M5 19h14" />,
  target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /></>,
};

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {ICONS[name]}
    </svg>
  );
}

/* ---------- form controls ---------- */

function NumberField({ label, value, onChange, error, unit, min, max, step }: {
  label: string; value: number; onChange: (value: number) => void; error?: string; unit?: string;
  min?: number; max?: number; step?: number | string;
}) {
  const id = useId();
  return (
    <div className={`field${error ? " invalid" : ""}`}>
      <label className="field-label" htmlFor={id}>{label}</label>
      <div className="input-wrap">
        <input id={id} type="number" inputMode="decimal" min={min} max={max} step={step}
          value={Number.isNaN(value) ? "" : value}
          onChange={(event) => onChange(event.target.value === "" ? NaN : Number(event.target.value))}
          aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} />
        {unit && <span className="unit">{unit}</span>}
      </div>
      {error && <small className="field-error" id={`${id}-error`}>{error}</small>}
    </div>
  );
}

function TextField({ label, value, onChange, maxLength }: {
  label: string; value: string; onChange: (value: string) => void; maxLength?: number;
}) {
  const id = useId();
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>{label}</label>
      <input id={id} value={value} maxLength={maxLength} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function SelectField({ label, value, onChange, options }: {
  label: string; value: string; onChange: (value: string) => void; options: string[];
}) {
  const id = useId();
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option}>{option}</option>)}
      </select>
    </div>
  );
}

function Segmented<T extends string>({ label, value, options, onChange, tone = "dark", hideLabel }: {
  label: string; value: T; options: { value: T; label: string }[]; onChange: (value: T) => void;
  tone?: "dark" | "light"; hideLabel?: boolean;
}) {
  return (
    <div className="field">
      <span className={hideLabel ? "sr-only" : "field-label"}>{label}</span>
      <div className={`segmented ${tone}`} role="radiogroup" aria-label={label}>
        {options.map((option) => (
          <button type="button" role="radio" key={option.value} aria-checked={value === option.value}
            className={value === option.value ? "on" : ""} onClick={() => onChange(option.value)}>
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ---------- charts ---------- */

function themeLayout(
  base: Record<string, any> | undefined, height: number, narrow: boolean, variant: "default" | "diurnal" | "scene",
): Record<string, any> {
  const rawTitle = base?.title;
  const titleText = typeof rawTitle === "string" ? rawTitle : rawTitle?.text;
  const layout: Record<string, any> = {
    ...base,
    autosize: true,
    height,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: FONT, color: "#27413f", size: narrow ? 11 : 12 },
    title: narrow || !titleText ? undefined : { text: titleText, x: 0, xanchor: "left", font: { size: 14 } },
  };
  if (variant === "scene") {
    layout.margin = { l: 0, r: 0, t: narrow ? 0 : 30, b: 0 };
  } else if (narrow) {
    layout.margin = { l: 44, r: 10, t: 28, b: variant === "diurnal" ? 130 : 44 };
  }
  if (variant === "diurnal" && narrow) {
    layout.legend = { orientation: "h", x: 0, y: -0.28, yanchor: "top" };
  }
  return layout;
}

function Chart({ figure, height, narrow, variant = "default" }: {
  figure: PlotFigure; height: number; narrow: boolean; variant?: "default" | "diurnal" | "scene";
}) {
  const layout = useMemo(() => themeLayout(figure.layout, height, narrow, variant), [figure, height, narrow, variant]);
  return <Plot data={figure.data} layout={layout} useResizeHandler style={{ width: "100%", height }} config={PLOT_CONFIG} />;
}

/* ---------- app ---------- */

function App() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [lastRun, setLastRun] = useState<FormState | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("spatial");
  const [summary, setSummary] = useState<any>(null);
  const [diurnal, setDiurnal] = useState<any>(null);
  const [spatial, setSpatial] = useState<any>(null);
  const [optimizer, setOptimizer] = useState<any[]>([]);
  const [optimizerRan, setOptimizerRan] = useState(false);
  const [optimizerLoading, setOptimizerLoading] = useState(false);
  const [hour, setHour] = useState(5);
  const [field, setField] = useState("do");
  const [depthLayer, setDepthLayer] = useState(0);
  const [contourView, setContourView] = useState("vertical");
  const [loading, setLoading] = useState(false);
  const [spatialLoading, setSpatialLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [error, setError] = useState("");
  const [panelError, setPanelError] = useState("");

  const spatialKey = useRef("");
  const didInit = useRef(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const settingsRef = useRef<HTMLButtonElement>(null);

  const narrow = useMediaQuery("(max-width: 640px)");
  const compact = useMediaQuery("(max-width: 960px)");

  const errors = useMemo(() => validate(form), [form]);
  const hasErrors = Object.keys(errors).length > 0;
  const dirty = Boolean(summary && lastRun && JSON.stringify(lastRun) !== JSON.stringify(form));
  const density = form.stocking_count / (form.length * form.width);

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const loadSimulation = async (event?: FormEvent) => {
    event?.preventDefault();
    if (hasErrors || loading) return;
    setLoading(true);
    setError("");
    setPanelError("");
    setPlaying(false);
    setDrawerOpen(false);
    try {
      const response = await fetch(`${API}/simulations`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      if (!response.ok) throw new Error(await errorMessage(response, "Simulation failed"));
      const next = await response.json();
      setSummary(next);
      setLastRun(form);
      setOptimizer([]);
      setOptimizerRan(false);
      setDepthLayer(next.config.nz - 1); // pond floor, where hypoxia shows up
      setHour(Math.min(next.report.min_bottom_do_hour, 24)); // open on the worst hour
    } catch (problem) {
      setError(describe(problem, "Simulation failed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    void loadSimulation();
  }, []);

  // 24-hour series for the current simulation
  useEffect(() => {
    if (!summary) return;
    const controller = new AbortController();
    getJson(`${API}/simulations/${summary.id}/diurnal`, controller.signal)
      .then(setDiurnal)
      .catch((problem) => { if (!isAbort(problem)) setPanelError(describe(problem, "Unable to load the 24-hour series")); });
    return () => controller.abort();
  }, [summary?.id]);

  // Spatial figures: refetch when any control changes, dropping superseded requests
  useEffect(() => {
    if (!summary || activeTab !== "spatial") return;
    const url = `${API}/simulations/${summary.id}/spatial?hour=${hour}&field=${field}&depth_layer=${depthLayer}&contour_view=${contourView}`;
    if (spatialKey.current === url) return;
    const controller = new AbortController();
    setSpatialLoading(true);
    getJson(url, controller.signal)
      .then((payload) => { spatialKey.current = url; setSpatial(payload); setPanelError(""); })
      .catch((problem) => { if (!isAbort(problem)) setPanelError(describe(problem, "Unable to load the spatial field")); })
      .finally(() => { if (!controller.signal.aborted) setSpatialLoading(false); });
    return () => controller.abort();
  }, [summary?.id, activeTab, hour, field, depthLayer, contourView]);

  // 24-hour animation: advance only after the current frame has loaded
  useEffect(() => {
    if (!playing || spatialLoading || activeTab !== "spatial") return;
    const timer = window.setTimeout(() => setHour((current) => (current >= 24 ? 0 : current + 1)), 450);
    return () => window.clearTimeout(timer);
  }, [playing, spatialLoading, hour, activeTab]);

  // Drawer behaviour on small screens
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setDrawerOpen(false); };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      settingsRef.current?.focus();
    };
  }, [drawerOpen]);

  useEffect(() => { if (!compact) setDrawerOpen(false); }, [compact]);

  const selectTab = (tab: Tab) => { setPlaying(false); setPanelError(""); setActiveTab(tab); };

  const onTabKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex((tab) => tab.key === activeTab);
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % TABS.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + TABS.length) % TABS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = TABS.length - 1;
    else return;
    event.preventDefault();
    selectTab(TABS[next].key);
    document.getElementById(`tab-${TABS[next].key}`)?.focus();
  };

  const runOptimizer = async () => {
    if (!summary) return;
    setOptimizerLoading(true);
    setPanelError("");
    try {
      const response = await fetch(`${API}/simulations/${summary.id}/optimizer`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(OPTIMIZER_COUNTS),
      });
      if (!response.ok) throw new Error(await errorMessage(response, "Scenario sweep failed"));
      const payload = await response.json();
      setOptimizer(payload.results ?? []);
      setOptimizerRan(true);
    } catch (problem) {
      setPanelError(describe(problem, "Unable to run the scenario sweep"));
    } finally {
      setOptimizerLoading(false);
    }
  };

  const report = summary?.report;
  const config = summary?.config;
  const liveFellBack = Boolean(summary && lastRun?.source === "live" && !summary.weather?.is_live_api);

  return (
    <div className="app-shell">
      <header className="mobile-bar">
        <img className="mobile-logo" src="/ecoprawn-logo.png" alt="EcoPrawn" />
        <div className="bar-actions">
          <button type="button" ref={settingsRef} className="bar-button" onClick={() => setDrawerOpen(true)}
            aria-expanded={drawerOpen} aria-controls="controls-drawer">
            <Icon name="sliders" /> Settings{dirty && <span className="badge-dot" aria-label="Unsaved changes" />}
          </button>
          <button type="button" className="bar-button primary" onClick={() => void loadSimulation()} disabled={loading || hasErrors}>
            <Icon name="play" size={14} /> {loading ? "Solving…" : "Run"}
          </button>
        </div>
      </header>

      <div className={`scrim${drawerOpen ? " show" : ""}`} onClick={() => setDrawerOpen(false)} aria-hidden="true" />

      <aside id="controls-drawer" className={`sidebar${drawerOpen ? " open" : ""}`} aria-label="Simulation settings">
        <div className="sidebar-head">
          <div className="brand">
            <img className="brand-logo" src="/ecoprawn-logo.png" alt="EcoPrawn" />
            <small>3D aquaculture simulation</small>
          </div>
          <button type="button" ref={closeRef} className="close-btn" onClick={() => setDrawerOpen(false)} aria-label="Close settings">
            <Icon name="close" />
          </button>
        </div>

        <form id="sim-form" onSubmit={loadSimulation} className="controls" noValidate>
          <fieldset className="group">
            <legend>Environment</legend>
            <Segmented label="Weather source" value={form.source} onChange={(value) => updateForm("source", value)}
              options={[{ value: "synthetic", label: "Synthetic model" }, { value: "live", label: "Live Open-Meteo" }]} />
            {form.source === "live" ? (
              <>
                <TextField label="Site label" value={form.location_name} maxLength={120} onChange={(value) => updateForm("location_name", value)} />
                <div className="split">
                  <NumberField label="Latitude" step="0.0001" min={-90} max={90} value={form.latitude} error={errors.latitude} onChange={(value) => updateForm("latitude", value)} />
                  <NumberField label="Longitude" step="0.0001" min={-180} max={180} value={form.longitude} error={errors.longitude} onChange={(value) => updateForm("longitude", value)} />
                </div>
                <p className="hint">If the weather service can't be reached, the run falls back to the synthetic model.</p>
              </>
            ) : (
              <SelectField label="Climate condition" value={form.weather_condition} onChange={(value) => updateForm("weather_condition", value)}
                options={["Sunny / Clear Skies", "Intermittent Clouds", "Overcast / Rainy"]} />
            )}
          </fieldset>

          <fieldset className="group">
            <legend>Pond</legend>
            <div className="split">
              <NumberField label="Length" unit="m" min={10} max={100} value={form.length} error={errors.length} onChange={(value) => updateForm("length", value)} />
              <NumberField label="Width" unit="m" min={10} max={100} value={form.width} error={errors.width} onChange={(value) => updateForm("width", value)} />
            </div>
            <NumberField label="Depth" unit="m" step="0.1" min={0.8} max={3} value={form.depth} error={errors.depth} onChange={(value) => updateForm("depth", value)} />
            <Segmented label="Grid resolution" value={form.grid} onChange={(value) => updateForm("grid", value)}
              options={[{ value: "fast", label: "Fast" }, { value: "standard", label: "Standard" }, { value: "high", label: "High-res" }]} />
          </fieldset>

          <fieldset className="group">
            <legend>Stocking and feed</legend>
            <NumberField label="Stocking count" unit="shrimp" step="1000" min={1000} max={200000} value={form.stocking_count}
              error={errors.stocking_count} onChange={(value) => updateForm("stocking_count", value)} />
            {Number.isFinite(density) && !errors.stocking_count && (
              <p className="hint">About {density.toFixed(1)} shrimp per m² of pond floor.</p>
            )}
            <div className="field">
              <div className="range-head">
                <label className="field-label" htmlFor="weight">Average shrimp weight</label>
                <output htmlFor="weight">{form.individual_weight_g} g</output>
              </div>
              <input id="weight" type="range" min={5} max={35} value={form.individual_weight_g}
                onChange={(event) => updateForm("individual_weight_g", Number(event.target.value))} />
            </div>
            <div className="field">
              <span className="field-label">Feed profile</span>
              <div className="choice-list" role="radiogroup" aria-label="Feed profile">
                {FEEDS.map((feed) => (
                  <button type="button" role="radio" key={feed.value} aria-checked={form.feed_type === feed.value}
                    className={`choice${form.feed_type === feed.value ? " on" : ""}`} onClick={() => updateForm("feed_type", feed.value)}>
                    <span className="choice-title">{feed.title}</span>
                    <span className="choice-sub">{feed.sub}</span>
                  </button>
                ))}
              </div>
            </div>
          </fieldset>

          <fieldset className="group">
            <legend>Aeration</legend>
            <label className="switch-row">
              <span>Paddlewheel aerators</span>
              <input type="checkbox" role="switch" checked={form.aeration_enabled}
                onChange={(event) => updateForm("aeration_enabled", event.target.checked)} />
              <span className="switch" aria-hidden="true" />
            </label>
            {form.aeration_enabled && (
              <>
                <div className="split">
                  <NumberField label="Start hour" min={0} max={23} value={form.aeration_start_hour} error={errors.aeration_start_hour}
                    onChange={(value) => updateForm("aeration_start_hour", value)} />
                  <NumberField label="End hour" min={0} max={23} value={form.aeration_end_hour} error={errors.aeration_end_hour}
                    onChange={(value) => updateForm("aeration_end_hour", value)} />
                </div>
                <p className="hint">Hours use a 24-hour clock. Aerators run from the start hour through the end hour.</p>
              </>
            )}
          </fieldset>
        </form>

        <div className="sidebar-foot">
          <button type="submit" form="sim-form" className="run-button" disabled={loading || hasErrors}>
            {loading ? <><span className="spinner" aria-hidden="true" /> Solving model…</> : <><Icon name="play" size={14} /> Run simulation</>}
          </button>
          <button type="button" className="ghost-button" onClick={() => setForm(initialForm)} disabled={loading}>Reset</button>
        </div>
      </aside>

      <main className="main" aria-busy={loading}>
        {loading && <div className="progress" role="progressbar" aria-label="Running simulation" />}

        <header className="hero">
          <div>
            <h1>Water quality, seen in three dimensions.</h1>
            <p className="lede">Step through a 24-hour cycle to see where oxygen runs out on the pond floor and what your stocking plan does about it.</p>
          </div>
          <span className={`chip source${summary?.weather?.is_live_api ? " live" : ""}`}>
            <span className="dot" />{summary?.weather?.source_name ?? "Preparing model"}
          </span>
        </header>

        {error && (
          <div className="banner danger" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        {liveFellBack && <div className="banner info" role="status"><span>Live weather wasn't available, so this run used the synthetic model.</span></div>}
        {dirty && !loading && (
          <div className="banner info" role="status">
            <span>Settings changed since the last run.</span>
            <button type="button" onClick={() => void loadSimulation()} disabled={hasErrors}>Run again</button>
          </div>
        )}

        {!summary && loading && <LoadingSkeleton />}
        {!summary && !loading && (
          <div className="empty-state">
            <h2>No simulation yet</h2>
            <p>Adjust the settings, then run the model to see oxygen and temperature through the pond.</p>
            <button type="button" className="btn" onClick={() => void loadSimulation()} disabled={hasErrors}>Run simulation</button>
          </div>
        )}

        {report && (
          <>
            <VerdictBanner report={report} />
            <div className="kpi-grid">
              <Kpi label="Lowest bottom DO" value={`${report.min_bottom_do.toFixed(2)} mg/L`}
                hint={`${Math.abs(report.min_bottom_do - HYPOXIA_LIMIT).toFixed(2)} ${report.min_bottom_do >= HYPOXIA_LIMIT ? "above" : "below"} the ${HYPOXIA_LIMIT} mg/L limit`}
                tone={report.min_bottom_do < LETHAL_LIMIT ? "danger" : report.min_bottom_do < HYPOXIA_LIMIT ? "warning" : "success"} />
              <Kpi label="Hypoxic hours" value={`${report.hypoxic_hours_count} h`} hint={`Bottom DO under ${HYPOXIA_LIMIT} mg/L`}
                tone={report.hypoxic_hours_count > 0 ? "warning" : "success"} />
              <Kpi label="Peak hypoxic volume" value={`${report.max_hypoxic_volume_pct.toFixed(1)}%`} hint="Share of the pond volume" />
              <Kpi label="Projected survival" value={`${report.projected_survival_rate_pct.toFixed(1)}%`} hint="At harvest" />
            </div>

            <div className="tabs" role="tablist" aria-label="Results" onKeyDown={onTabKeyDown}>
              {TABS.map((tab) => (
                <button type="button" role="tab" key={tab.key} id={`tab-${tab.key}`} aria-selected={activeTab === tab.key}
                  aria-controls={`panel-${tab.key}`} tabIndex={activeTab === tab.key ? 0 : -1}
                  className={`tab${activeTab === tab.key ? " active" : ""}`} onClick={() => selectTab(tab.key)}>
                  {tab.label}
                </button>
              ))}
            </div>

            {panelError && <div className="banner danger" role="alert"><span>{panelError}</span><button type="button" onClick={() => setPanelError("")}>Dismiss</button></div>}

            <div role="tabpanel" id={`panel-${activeTab}`} aria-labelledby={`tab-${activeTab}`} className={`panel${loading ? " dimmed" : ""}`}>
              {activeTab === "spatial" && (
                <SpatialView spatial={spatial} loading={spatialLoading} hour={hour} field={field} depthLayer={depthLayer}
                  config={config} report={report} contourView={contourView} playing={playing} narrow={narrow}
                  setHour={(value) => { setPlaying(false); setHour(value); }} setField={setField} setDepthLayer={setDepthLayer}
                  setContourView={setContourView} setPlaying={setPlaying} jumpToCritical={() => { setPlaying(false); setHour(report.min_bottom_do_hour); }} />
              )}
              {activeTab === "diurnal" && (
                <section className="section">
                  <SectionHeading title="The pond breathes on a 24-hour cycle"
                    text="Photosynthesis adds oxygen by day and respiration draws it down at night. The risk window is just before dawn." />
                  <div className="plot-panel">
                    {diurnal ? <Chart figure={diurnal.figure} height={narrow ? 560 : 540} narrow={narrow} variant="diurnal" /> : <div className="skeleton plot-skeleton" />}
                  </div>
                  <p className="hint dark">Bottom DO under {HYPOXIA_LIMIT} mg/L is hypoxic and under {LETHAL_LIMIT} mg/L is lethal for <em>Penaeus vannamei</em>.</p>
                </section>
              )}
              {activeTab === "feasibility" && <FeasibilityView report={report} config={config} />}
              {activeTab === "optimizer" && <OptimizerView rows={optimizer} ran={optimizerRan} run={runOptimizer} loading={optimizerLoading} />}
              {activeTab === "report" && <ReportView id={summary.id} />}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

/* ---------- views ---------- */

function LoadingSkeleton() {
  return (
    <div aria-hidden="true">
      <div className="skeleton" style={{ height: 92, marginBottom: 14 }} />
      <div className="kpi-grid">
        {[0, 1, 2, 3].map((item) => <div className="skeleton" style={{ height: 104 }} key={item} />)}
      </div>
      <div className="skeleton" style={{ height: 360 }} />
    </div>
  );
}

function VerdictBanner({ report }: { report: any }) {
  const tone = verdictTone(report.verdict);
  const icon = tone === "success" ? "check" : tone === "danger" ? "cross" : "alert";
  return (
    <section className={`verdict ${tone}`} aria-live="polite">
      <span className="verdict-icon"><Icon name={icon} size={22} /></span>
      <div className="verdict-text">
        <h2>{sentence(report.verdict)}</h2>
        <p>{report.primary_reason}</p>
      </div>
      <div className="verdict-stat">
        <strong>{report.min_bottom_do.toFixed(2)} <small>mg/L</small></strong>
        <span>lowest bottom DO at {pad(report.min_bottom_do_hour)}:00</span>
      </div>
    </section>
  );
}

function Kpi({ label, value, hint, tone }: { label: string; value: string; hint: string; tone?: "success" | "warning" | "danger" }) {
  return (
    <div className={`kpi${tone ? ` tone-${tone}` : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}

function SectionHeading({ title, text }: { title: string; text: string }) {
  return <div className="section-heading"><h2>{title}</h2><p>{text}</p></div>;
}

function SpatialView(props: {
  spatial: any; loading: boolean; hour: number; field: string; depthLayer: number; config: any; report: any;
  contourView: string; playing: boolean; narrow: boolean;
  setHour: (value: number) => void; setField: (value: string) => void; setDepthLayer: (value: number) => void;
  setContourView: (value: string) => void; setPlaying: (value: boolean) => void; jumpToCritical: () => void;
}) {
  const { spatial, loading, hour, field, depthLayer, config, report, contourView, playing, narrow } = props;
  const layerLabel = (index: number) => {
    const depth = (config.depth * index) / (config.nz - 1);
    const tag = index === 0 ? ", surface" : index === config.nz - 1 ? ", bottom" : "";
    return `Layer ${index + 1} (${depth.toFixed(2)} m${tag})`;
  };
  const fieldName = field === "do" ? "dissolved oxygen" : "temperature";

  return (
    <section className="section">
      <SectionHeading title="Explore the pond, field by field"
        text="Inspect oxygen depletion, thermal stratification and the pond floor at any hour." />

      <div className="toolbar">
        <div className="control time">
          <label htmlFor="hour">Time of day</label>
          <div className="time-row">
            <button type="button" className="icon-btn" onClick={() => props.setPlaying(!playing)}
              aria-label={playing ? "Pause animation" : "Play the 24-hour animation"}>
              <Icon name={playing ? "pause" : "play"} size={16} />
            </button>
            <input id="hour" type="range" min={0} max={24} value={hour} onChange={(event) => props.setHour(Number(event.target.value))} />
            <output htmlFor="hour">{pad(hour)}:00</output>
          </div>
        </div>
        <Segmented tone="light" label="Field" value={field} onChange={props.setField}
          options={[{ value: "do", label: "Oxygen" }, { value: "temp", label: "Temperature" }]} />
        <div className="control">
          <label htmlFor="layer">Depth layer</label>
          <select id="layer" value={depthLayer} onChange={(event) => props.setDepthLayer(Number(event.target.value))}>
            {Array.from({ length: config.nz }, (_, index) => <option value={index} key={index}>{layerLabel(index)}</option>)}
          </select>
        </div>
        <button type="button" className="btn-ghost" onClick={props.jumpToCritical}>
          <Icon name="target" size={16} /> Lowest DO ({pad(report.min_bottom_do_hour)}:00)
        </button>
      </div>

      {!spatial ? (
        <div className="plot-grid"><div className="skeleton plot-skeleton" /><div className="skeleton plot-skeleton" /></div>
      ) : (
        <div className={loading ? "dimmed" : ""} aria-busy={loading}>
          <div className="plot-grid">
            <div className="plot-panel">
              <div className="panel-head"><h3>3D volume: {fieldName}</h3><span>Orange shapes are representative shrimp</span></div>
              <Chart figure={spatial.volume} height={narrow ? 340 : 540} narrow={narrow} variant="scene" />
            </div>
            <div className="plot-panel">
              <div className="panel-head"><h3>Horizontal slice</h3><span>Depth {spatial.depth.toFixed(2)} m</span></div>
              <Chart figure={spatial.heatmap} height={narrow ? 320 : 430} narrow={narrow} />
            </div>
          </div>

          <div className="plot-panel wide">
            <div className="panel-head">
              <h3>2D contour profiles</h3>
              <Segmented tone="light" hideLabel label="Contour plane" value={contourView} onChange={props.setContourView}
                options={[{ value: "vertical", label: "Vertical cross-section" }, { value: "benthic", label: "Pond floor" }]} />
            </div>
            <div className="plot-scroll">
              <div className="plot-inner">
                <Chart figure={spatial.contours} height={narrow ? 400 : 520} narrow={narrow} />
              </div>
            </div>
            {narrow && <p className="hint dark">Swipe sideways to see both profiles.</p>}
          </div>
        </div>
      )}
    </section>
  );
}

function DoGauge({ value }: { value: number }) {
  const max = 8;
  const at = (amount: number) => `${Math.max(0, Math.min(100, (amount / max) * 100))}%`;
  return (
    <div className="gauge" role="img"
      aria-label={`Lowest bottom DO is ${value.toFixed(2)} mg/L. Lethal below ${LETHAL_LIMIT}, hypoxic below ${HYPOXIA_LIMIT}.`}>
      <div className="gauge-track">
        <span className="zone lethal" style={{ left: 0, width: at(LETHAL_LIMIT) }} />
        <span className="zone hypoxic" style={{ left: at(LETHAL_LIMIT), width: `calc(${at(HYPOXIA_LIMIT)} - ${at(LETHAL_LIMIT)})` }} />
        <span className="zone safe" style={{ left: at(HYPOXIA_LIMIT), right: 0 }} />
        <span className="gauge-marker" style={{ left: at(value) }} />
      </div>
      <div className="gauge-scale" aria-hidden="true">
        <span style={{ left: 0 }}>0</span>
        <span style={{ left: at(LETHAL_LIMIT) }}>{LETHAL_LIMIT}</span>
        <span style={{ left: at(HYPOXIA_LIMIT) }}>{HYPOXIA_LIMIT}</span>
        <span style={{ left: "100%" }}>{max}+</span>
      </div>
    </div>
  );
}

function FeasibilityView({ report, config }: { report: any; config: any }) {
  return (
    <section className="section">
      <SectionHeading title="Is this pond carrying the plan?"
        text="The verdict combines oxygen gradients, stocking density and the pond's biological carrying capacity." />
      <div className="detail-grid">
        <div className="card">
          <h3>{sentence(report.verdict)}</h3>
          <p>{report.primary_reason}</p>
          <ul className="reasons">{report.detailed_reasons.map((reason: string) => <li key={reason}>{reason}</li>)}</ul>
          {report.aeration_schedule_recommendation && <div className="recommendation">{report.aeration_schedule_recommendation}</div>}
        </div>
        <div className="card">
          <h3>Oxygen margin</h3>
          <DoGauge value={report.min_bottom_do} />
          <div className="metrics">
            <MetricRow label="Stocking count" value={`${config.stocking_count.toLocaleString()} juveniles`} />
            <MetricRow label="Floor density" value={`${report.stocking_density_m2.toFixed(1)} shrimp/m²`} />
            <MetricRow label="Carrying status" value={report.carrying_capacity_status} />
            <MetricRow label="Projected survival" value={`${report.projected_survival_rate_pct.toFixed(1)}%`} />
            <MetricRow label="Harvest biomass" value={`${report.projected_harvest_biomass_kg.toFixed(1)} kg`} />
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return <div className="metric-row"><span>{label}</span><strong>{value}</strong></div>;
}

function OptimizerView({ rows, ran, run, loading }: { rows: any[]; ran: boolean; run: () => void; loading: boolean }) {
  const feeds = Array.from(new Set(rows.map((row) => row.feed_type as string)));
  const viable = feeds.map((feed) => {
    const counts = rows.filter((row) => row.feed_type === feed && row.verdict !== "NOT FEASIBLE").map((row) => row.stocking_count as number);
    return { feed, max: counts.length ? Math.max(...counts) : null };
  });

  return (
    <section className="section">
      <SectionHeading title="Find the sustainable edge of capacity"
        text="Compare stocking counts and feed regimes against the hypoxia tipping point. The sweep runs ten coarse simulations." />
      <button type="button" className="btn" onClick={run} disabled={loading}>
        {loading ? <><span className="spinner" aria-hidden="true" /> Running capacity sweep…</> : ran ? "Run the sweep again" : "Run capacity sweep"}
      </button>

      {!ran && !loading && <p className="hint dark">Tests {OPTIMIZER_COUNTS.map((count) => count.toLocaleString()).join(", ")} shrimp with each feed profile.</p>}

      {rows.length > 0 && (
        <>
          <div className="viable-grid">
            {viable.map((item) => (
              <div className="stat" key={item.feed}>
                <span>{item.feed.replace(" Feed", "")}</span>
                <strong>{item.max ? `Up to ${item.max.toLocaleString()}` : "None viable"}</strong>
                <small>{item.max ? "highest stocking tested that isn't marked not feasible" : "every tested count is not feasible"}</small>
              </div>
            ))}
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th scope="col">Stocking</th><th scope="col">Feed</th><th scope="col">Lowest bottom DO</th><th scope="col">Verdict</th><th scope="col">Harvest biomass</th></tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.stocking_count}-${row.feed_type}`}>
                    <td data-label="Stocking">{row.stocking_count.toLocaleString()}</td>
                    <td data-label="Feed">{row.feed_type.replace(" Feed", "")}</td>
                    <td data-label="Lowest bottom DO">
                      <span className="do-cell">
                        <span className="meter" aria-hidden="true"><i style={{ width: `${Math.min(100, (row.min_bottom_do / 8) * 100)}%` }} /></span>
                        {row.min_bottom_do.toFixed(2)} mg/L
                      </span>
                    </td>
                    <td data-label="Verdict"><span className={`chip tone-${verdictTone(row.verdict)}`}>{sentence(row.verdict)}</span></td>
                    <td data-label="Harvest biomass">{row.harvest_biomass_kg.toFixed(1)} kg</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function ReportView({ id }: { id: string }) {
  const [html, setHtml] = useState(reportCache.get(id) ?? "");
  const [loading, setLoading] = useState(!reportCache.has(id));
  const [failed, setFailed] = useState("");

  useEffect(() => {
    if (reportCache.has(id)) { setHtml(reportCache.get(id)!); setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    setFailed("");
    fetch(`${API}/simulations/${id}/report`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(await errorMessage(response, "Report generation failed"));
        return response.text();
      })
      .then((text) => { reportCache.set(id, text); setHtml(text); })
      .catch((problem) => { if (!isAbort(problem)) setFailed(describe(problem, "Report generation failed")); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id]);

  return (
    <section className="section">
      <SectionHeading title="A publication-ready record of the run"
        text="The report includes the contour figures and the full feasibility reasoning." />
      <a className="btn link-button" href={`${API}/simulations/${id}/report`} download={`EcoPrawn_Report_${id}.html`}>
        <Icon name="download" size={16} /> Download HTML report
      </a>
      {failed && <div className="banner danger" role="alert"><span>{failed}</span></div>}
      {loading ? (
        <div className="empty-state compact"><div className="loader" /><p>Rendering report figures…</p></div>
      ) : html ? (
        <div className="report-preview"><iframe title="EcoPrawn research report" srcDoc={html} /></div>
      ) : null}
    </section>
  );
}

export default App;