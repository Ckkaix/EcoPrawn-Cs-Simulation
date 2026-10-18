import { FormEvent, useEffect, useState } from "react";
import Plot from "react-plotly.js";

const API = import.meta.env.VITE_API_URL ?? "/api";
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

function App() {
  const [form, setForm] = useState(initialForm);
  const [activeTab, setActiveTab] = useState<Tab>("spatial");
  const [summary, setSummary] = useState<any>(null);
  const [diurnal, setDiurnal] = useState<any>(null);
  const [spatial, setSpatial] = useState<any>(null);
  const [optimizer, setOptimizer] = useState<any[]>([]);
  const [optimizerLoading, setOptimizerLoading] = useState(false);
  const [hour, setHour] = useState(5);
  const [field, setField] = useState("do");
  const [depthLayer, setDepthLayer] = useState(-1);
  const [contourView, setContourView] = useState("vertical");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const updateForm = (key: keyof FormState, value: string | number | boolean) =>
    setForm((current) => ({ ...current, [key]: value }));

  const loadSimulation = async (event?: FormEvent) => {
    event?.preventDefault();
    setLoading(true); setError("");
    try {
      const response = await fetch(`${API}/simulations`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Simulation failed");
      const nextSummary = await response.json();
      setSummary(nextSummary);
      const [nextDiurnal, nextSpatial] = await Promise.all([
        fetch(`${API}/simulations/${nextSummary.id}/diurnal`).then((item) => item.json()),
        fetch(`${API}/simulations/${nextSummary.id}/spatial?hour=${hour}&field=${field}&depth_layer=${depthLayer}&contour_view=${contourView}`).then((item) => item.json()),
      ]);
      setDiurnal(nextDiurnal); setSpatial(nextSpatial);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Unable to reach the EcoPrawn API");
    } finally { setLoading(false); }
  };

  const refreshSpatial = async (nextHour = hour, nextField = field, nextDepth = depthLayer, nextContourView = contourView) => {
    if (!summary) return;
    const response = await fetch(`${API}/simulations/${summary.id}/spatial?hour=${nextHour}&field=${nextField}&depth_layer=${nextDepth}&contour_view=${nextContourView}`);
    setSpatial(await response.json());
  };

  useEffect(() => { void loadSimulation(); }, []);

  const report = summary?.report;
  const config = summary?.config;
  const setHourAndRefresh = (value: number) => { setHour(value); void refreshSpatial(value, field, depthLayer); };
  const setFieldAndRefresh = (value: string) => { setField(value); void refreshSpatial(hour, value, depthLayer); };
  const setDepthAndRefresh = (value: number) => { setDepthLayer(value); void refreshSpatial(hour, field, value); };
  const setContourViewAndRefresh = (value: string) => { setContourView(value); void refreshSpatial(hour, field, depthLayer, value); };

  const runOptimizer = async () => {
    if (!summary) return;
    setOptimizerLoading(true); setError("");
    try {
      const response = await fetch(`${API}/simulations/${summary.id}/optimizer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify([10000, 20000, 30000, 40000, 50000]) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Scenario sweep failed");
      setOptimizer(payload.results ?? []);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Unable to run the scenario sweep");
    } finally { setOptimizerLoading(false); }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><img className="brand-logo" src="/ecoprawn-logo.png" alt="EcoPrawn" /><div><small>3D AQUACULTURE SIMULATION</small></div></div>
        <div className="side-intro"><p>Simulate pond water quality, shrimp stocking, and production feasibility.</p></div>
        <form onSubmit={loadSimulation} className="controls">
          <section><div className="section-label"><span>01</span> ENVIRONMENT</div>
            <select value={form.source} onChange={(e) => updateForm("source", e.target.value)}><option value="synthetic">Synthetic diurnal model</option><option value="live">Live Open-Meteo API</option></select>
            {form.source === "live" && <><label>Site label<input value={form.location_name} onChange={(e) => updateForm("location_name", e.target.value)} /></label><div className="split"><label>Latitude<input type="number" step="0.0001" value={form.latitude} onChange={(e) => updateForm("latitude", Number(e.target.value))} /></label><label>Longitude<input type="number" step="0.0001" value={form.longitude} onChange={(e) => updateForm("longitude", Number(e.target.value))} /></label></div></>}
            {form.source === "synthetic" && <label>Climate condition<select value={form.weather_condition} onChange={(e) => updateForm("weather_condition", e.target.value)}><option>Sunny / Clear Skies</option><option>Intermittent Clouds</option><option>Overcast / Rainy</option></select></label>}
          </section>
          <section><div className="section-label"><span>02</span> POND GEOMETRY</div><div className="split"><label>Length X<input type="number" value={form.length} onChange={(e) => updateForm("length", Number(e.target.value))} /></label><label>Width Y<input type="number" value={form.width} onChange={(e) => updateForm("width", Number(e.target.value))} /></label></div><div className="split"><label>Depth Z<input type="number" step="0.1" value={form.depth} onChange={(e) => updateForm("depth", Number(e.target.value))} /></label><label>Grid<select value={form.grid} onChange={(e) => updateForm("grid", e.target.value)}><option value="fast">Fast</option><option value="standard">Standard</option><option value="high">High-res</option></select></label></div></section>
          <section><div className="section-label"><span>03</span> STOCKING & FEED</div><label>Stocking count<input type="number" step="1000" value={form.stocking_count} onChange={(e) => updateForm("stocking_count", Number(e.target.value))} /></label><label>Average shrimp weight <b>{form.individual_weight_g}g</b><input type="range" min="5" max="35" value={form.individual_weight_g} onChange={(e) => updateForm("individual_weight_g", Number(e.target.value))} /></label><label>Feed profile<select value={form.feed_type} onChange={(e) => updateForm("feed_type", e.target.value)}><option>Ordinary Commercial Feed</option><option>Fortified Growth-Booster Feed</option></select></label></section>
          <section><div className="section-label"><span>04</span> AERATION</div><label className="toggle-row"><span>Paddlewheel aerators</span><input type="checkbox" checked={form.aeration_enabled} onChange={(e) => updateForm("aeration_enabled", e.target.checked)} /></label>{form.aeration_enabled && <div className="split"><label>Start<input type="number" min="0" max="23" value={form.aeration_start_hour} onChange={(e) => updateForm("aeration_start_hour", Number(e.target.value))} /></label><label>End<input type="number" min="0" max="23" value={form.aeration_end_hour} onChange={(e) => updateForm("aeration_end_hour", Number(e.target.value))} /></label></div>}</section>
          <button className="run-button" disabled={loading}>{loading ? "SOLVING PDE MODEL..." : "RUN SIMULATION  →"}</button>
        </form>
      </aside>
      <main className="main-content">
        <header className="topbar"><div><h1>Water quality, seen in three dimensions.</h1></div><div className="live-status"><span className="status-dot" />{summary?.weather?.source_name ?? "Preparing model"}</div></header>
        {error && <div className="error-banner">{error}</div>}
        {report && <><div className={`alert ${report.verdict === "FEASIBLE" ? "success" : report.verdict === "NOT FEASIBLE" ? "danger" : "warning"}`}><strong>{report.verdict}</strong><span>{report.primary_reason}</span><b>{report.min_bottom_do.toFixed(2)} mg/L at {String(report.min_bottom_do_hour).padStart(2, "0")}:00</b></div><div className="kpi-grid"><Kpi label="MIN BOTTOM DO" value={`${report.min_bottom_do.toFixed(2)} mg/L`} hint={`${(report.min_bottom_do - 3.5).toFixed(2)} vs safety`} /><Kpi label="HYPOXIC HOURS" value={`${report.hypoxic_hours_count} hrs`} hint="below 3.5 mg/L" /><Kpi label="PEAK HYPOXIC VOL" value={`${report.max_hypoxic_volume_pct.toFixed(1)}%`} hint="of pond volume" /></div></>}
        <nav className="tabs">{([["spatial", "Spatial field"], ["diurnal", "24-hour dynamics"], ["feasibility", "Feasibility"], ["optimizer", "Scenario optimizer"], ["report", "Research report"]] as [Tab, string][]).map(([key, label]) => <button className={activeTab === key ? "active" : ""} key={key} onClick={() => setActiveTab(key)}>{label}</button>)}</nav>
        {!summary && loading && <div className="empty-state"><div className="loader" /><h2>Solving the pond model</h2><p>Initializing the 3D diffusion engine across the 24-hour cycle.</p></div>}
        {summary && activeTab === "spatial" && <SpatialView spatial={spatial} hour={hour} field={field} depthLayer={depthLayer} config={config} setHour={setHourAndRefresh} setField={setFieldAndRefresh} setDepthLayer={setDepthAndRefresh} contourView={contourView} setContourView={setContourViewAndRefresh} />}
        {summary && activeTab === "diurnal" && <section className="content-section"><SectionHeading kicker="DIURNAL DYNAMICS" title="The pond breathes on a 24-hour cycle" text="Track photosynthetic oxygen production, nocturnal respiration, and the pre-dawn risk window." />{diurnal && <Plot data={diurnal.figure.data} layout={{ ...diurnal.figure.layout, autosize: true }} useResizeHandler style={{ width: "100%", height: "520px" }} config={{ responsive: true, displaylogo: false }} />}</section>}
        {summary && activeTab === "feasibility" && <FeasibilityView report={report} config={config} />}
        {summary && activeTab === "optimizer" && <OptimizerView rows={optimizer} run={runOptimizer} loading={optimizerLoading} />}
        {summary && activeTab === "report" && <ReportView id={summary.id} />}
      </main>
    </div>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) { return <div className="kpi"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>; }
function SectionHeading({ kicker, title, text }: { kicker: string; title: string; text: string }) { return <div className="section-heading"><span className="eyebrow">{kicker}</span><h2>{title}</h2><p>{text}</p></div>; }
function SpatialView({ spatial, hour, field, depthLayer, config, setHour, setField, setDepthLayer, contourView, setContourView }: any) { return <section className="content-section"><SectionHeading kicker="SPATIAL GRADIENTS" title="Explore the pond field by field" text="Inspect oxygen depletion, thermal stratification, and the benthic habitat at any hour." /><div className="toolbar"><label>TIME <input type="range" min="0" max="24" value={hour} onChange={(e) => setHour(Number(e.target.value))} /><b>{String(hour).padStart(2, "0")}:00</b></label><label>FIELD<select value={field} onChange={(e) => setField(e.target.value)}><option value="do">Dissolved oxygen</option><option value="temp">Temperature</option></select></label><label>DEPTH LAYER<select value={depthLayer} onChange={(e) => setDepthLayer(Number(e.target.value))}>{Array.from({ length: config.nz }, (_, index) => <option value={index} key={index}>Layer {index + 1}</option>)}</select></label></div>{spatial && <><div className="plot-grid"><div className="plot-panel"><span className="plot-label">3D VOLUME / {field === "do" ? "DISSOLVED OXYGEN" : "TEMPERATURE"}</span><Plot data={spatial.volume.data} layout={{ ...spatial.volume.layout, autosize: true }} useResizeHandler style={{ width: "100%", height: "560px" }} config={{ responsive: true, displaylogo: false }} /></div><div className="plot-panel"><span className="plot-label">HORIZONTAL SLICE / DEPTH {spatial.depth.toFixed(2)}M</span><Plot data={spatial.heatmap.data} layout={{ ...spatial.heatmap.layout, autosize: true }} useResizeHandler style={{ width: "100%", height: "440px" }} config={{ responsive: true, displaylogo: false }} /></div></div><div className="contour-section"><div className="contour-controls"><span className="plot-label">THESIS-GRADE 2D CONTOUR PROFILES</span><label><input type="radio" checked={contourView === "vertical"} onChange={() => setContourView("vertical")} /> Vertical cross-section (X-Z depth plane)</label><label><input type="radio" checked={contourView === "benthic"} onChange={() => setContourView("benthic")} /> Benthic floor habitat (X-Y floor plane)</label></div><Plot data={spatial.contours.data} layout={{ ...spatial.contours.layout, autosize: true }} useResizeHandler style={{ width: "100%", height: "520px" }} config={{ responsive: true, displaylogo: false }} /></div></>}</section>; }
function FeasibilityView({ report, config }: any) { return <section className="content-section"><SectionHeading kicker="BIOLOGICAL OUTLOOK" title="Is this pond carrying the plan?" text="The verdict combines spatial dissolved oxygen gradients, stocking density, and biological carrying capacity." /><div className="detail-grid"><div className="detail-card"><span className="plot-label">TECHNICAL VERDICT</span><h3>{report.verdict}</h3><p>{report.primary_reason}</p><ul>{report.detailed_reasons.map((reason: string) => <li key={reason}>{reason}</li>)}</ul>{report.aeration_schedule_recommendation && <div className="recommendation">{report.aeration_schedule_recommendation}</div>}</div><div className="detail-card"><span className="plot-label">POND & PRODUCTION</span><MetricRow label="Stocking count" value={`${config.stocking_count.toLocaleString()} juveniles`} /><MetricRow label="Floor density" value={`${report.stocking_density_m2.toFixed(1)} shrimp/m²`} /><MetricRow label="Carrying status" value={report.carrying_capacity_status} /><MetricRow label="Projected survival" value={`${report.projected_survival_rate_pct.toFixed(1)}%`} /><MetricRow label="Harvest biomass" value={`${report.projected_harvest_biomass_kg.toFixed(1)} kg`} /></div></div></section>; }
function MetricRow({ label, value }: { label: string; value: string }) { return <div className="metric-row"><span>{label}</span><strong>{value}</strong></div>; }
function OptimizerView({ rows, run, loading }: { rows: any[]; run: () => void; loading: boolean }) { return <section className="content-section"><SectionHeading kicker="SCENARIO OPTIMIZER" title="Find the sustainable edge of capacity" text="Compare stocking density and feed regimes against the hypoxia tipping point." /><button className="secondary-button" onClick={run} disabled={loading}>{loading ? "RUNNING CAPACITY SWEEP..." : "RUN CAPACITY SWEEP  →"}</button>{rows.length > 0 && <div className="table-wrap"><table><thead><tr><th>Stocking</th><th>Feed</th><th>Min bottom DO</th><th>Verdict</th><th>Harvest biomass</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.stocking_count}-${row.feed_type}`}><td>{row.stocking_count.toLocaleString()}</td><td>{row.feed_type.replace(" Feed", "")}</td><td>{row.min_bottom_do.toFixed(2)} mg/L</td><td><span className="table-status">{row.verdict}</span></td><td>{row.harvest_biomass_kg.toFixed(1)} kg</td></tr>)}</tbody></table></div>}</section>; }
function ReportView({ id }: { id: string }) { const [html, setHtml] = useState(""); const [loading, setLoading] = useState(true); useEffect(() => { setLoading(true); fetch(`${API}/simulations/${id}/report`).then((response) => { if (!response.ok) throw new Error("Report generation failed"); return response.text(); }).then(setHtml).finally(() => setLoading(false)); }, [id]); return <section className="content-section"><SectionHeading kicker="RESEARCH REPORT" title="A publication-ready record of the run" text="Generate the technical report with embedded contour figures and the complete feasibility reasoning." /><a className="secondary-button link-button" href={`${API}/simulations/${id}/report`} download={`EcoPrawn_Report_${id}.html`}>DOWNLOAD HTML REPORT  ↓</a>{loading ? <div className="empty-state"><div className="loader" /><p>Rendering report figures...</p></div> : <div className="report-preview"><iframe title="EcoPrawn research report" srcDoc={html} /></div>}</section>; }

export default App;