"""REST API for the EcoPrawn simulation dashboard."""

from dataclasses import asdict, is_dataclass
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from ingestion.api_client import EnvironmentalAPIClient, WeatherData24H
from ingestion.synthetic_data import SyntheticDataGenerator
from models.diffusion_engine import Pond3DDiffusionSolver, SimulationConfig, SimulationResult
from models.optimizer import StockingOptimizer
from models.stocking_feed_simulator import FEED_PROFILES, FeedType, StockingFeedSimulator
from reporting.report_generator import FeasibilityReportGenerator
from visualization.interactive_3d import InteractivePlotter


app = FastAPI(title="EcoPrawn API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    error_messages = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x != "body"]
        field_name = " -> ".join(loc) if loc else "request"
        msg = err.get("msg", "Invalid value")
        error_messages.append(f"{field_name}: {msg}")
    
    formatted_detail = "Validation Error: " + "; ".join(error_messages)
    return JSONResponse(
        status_code=422,
        content={"detail": formatted_detail, "errors": exc.errors()},
    )


simulations: Dict[str, Dict[str, Any]] = {}
FINANCIAL_REPORT_FIELDS = {
    "total_feed_cost_php",
    "seed_stocking_cost_php",
    "total_operating_cost_php",
    "gross_revenue_php",
    "net_margin_php",
    "roi_percentage",
}
FINANCIAL_SCENARIO_FIELDS = {"feed_cost_php", "total_cost_php", "net_profit_php", "roi_pct"}


class SimulationRequest(BaseModel):
    source: str = Field(default="synthetic")
    latitude: float = Field(default=14.7565, ge=-90, le=90)
    longitude: float = Field(default=121.0441, ge=-180, le=180)
    location_name: str = Field(default="Caloocan City, Metro Manila", max_length=120)
    weather_condition: str = Field(default="Sunny / Clear Skies")
    length: float = Field(default=20.0, ge=5.0, le=200.0)
    width: float = Field(default=20.0, ge=5.0, le=200.0)
    depth: float = Field(default=1.5, ge=0.5, le=4.0)
    grid: str = Field(default="standard")
    stocking_count: int = Field(default=18000, ge=500, le=300000)
    individual_weight_g: float = Field(default=18.0, ge=2.0, le=45.0)
    feed_type: str = Field(default=FeedType.ORDINARY.value)
    aeration_enabled: bool = False
    aeration_start_hour: int = Field(default=1, ge=0, le=23)
    aeration_end_hour: int = Field(default=6, ge=0, le=23)


def _plain(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key.value if isinstance(key, FeedType) else key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, FeedType):
        return value.value
    return value


def _figure_json(figure: Any) -> Dict[str, Any]:
    return json.loads(figure.to_json())


def _public_report(report: Any) -> Dict[str, Any]:
    return {key: value for key, value in _plain(report).items() if key not in FINANCIAL_REPORT_FIELDS}


def _public_scenario(item: Any) -> Dict[str, Any]:
    return {key: value for key, value in _plain(item).items() if key not in FINANCIAL_SCENARIO_FIELDS}


def _weather(request: SimulationRequest) -> WeatherData24H:
    client = EnvironmentalAPIClient()
    if request.source == "live":
        live = client.fetch_open_meteo(
            lat=request.latitude,
            lon=request.longitude,
            location_label=request.location_name,
        )
        if live:
            return live
    return SyntheticDataGenerator.generate_diurnal_weather(weather_type=request.weather_condition)


def _grid_dimensions(grid: str) -> tuple[int, int, int]:
    return {
        "fast": (12, 12, 8),
        "high": (30, 30, 12),
        "standard": (20, 20, 10),
    }.get(grid, (20, 20, 10))


def _lookup(simulation_id: str) -> Dict[str, Any]:
    simulation = simulations.get(simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "ecoprawn-api"}


@app.post("/api/simulations")
def create_simulation(request: SimulationRequest) -> Dict[str, Any]:
    weather = _weather(request)
    nx, ny, nz = _grid_dimensions(request.grid)
    feed_type = FeedType(request.feed_type)
    profile = FEED_PROFILES[feed_type]
    config = SimulationConfig(
        length=request.length,
        width=request.width,
        depth=request.depth,
        nx=nx,
        ny=ny,
        nz=nz,
        stocking_count=request.stocking_count,
        individual_weight_g=request.individual_weight_g,
        feed_protein_ratio=profile.protein_percent / 100.0,
        feed_bod_factor=profile.bod_oxygen_factor,
        aeration_enabled=request.aeration_enabled,
        aeration_start_hour=request.aeration_start_hour,
        aeration_end_hour=request.aeration_end_hour,
    )
    result = Pond3DDiffusionSolver(config).solve(
        solar_irradiance=weather.solar_irradiance,
        air_temperature=weather.air_temperature,
        initial_temp=weather.initial_water_temp_c,
        initial_do=weather.initial_do_mg_l,
        dt_seconds=30.0,
    )
    report = StockingFeedSimulator().evaluate(config, result, feed_type)
    simulation_id = str(uuid4())
    simulations[simulation_id] = {
        "config": config,
        "result": result,
        "report": report,
        "feed_type": feed_type,
        "weather": weather,
    }
    return _summary(simulation_id, simulations[simulation_id])


def _summary(simulation_id: str, simulation: Dict[str, Any]) -> Dict[str, Any]:
    report = simulation["report"]
    config = simulation["config"]
    weather = simulation["weather"]
    return {
        "id": simulation_id,
        "config": _plain(config),
        "report": _public_report(report),
        "weather": _plain(weather),
        "feed_profile": _plain(FEED_PROFILES[simulation["feed_type"]]),
    }


@app.get("/api/simulations/{simulation_id}")
def get_simulation(simulation_id: str) -> Dict[str, Any]:
    return _summary(simulation_id, _lookup(simulation_id))


@app.get("/api/simulations/{simulation_id}/diurnal")
def get_diurnal(simulation_id: str) -> Dict[str, Any]:
    simulation = _lookup(simulation_id)
    result: SimulationResult = simulation["result"]
    return {
        "figure": _figure_json(InteractivePlotter.create_interactive_diurnal_chart(result)),
        "timestamps": _plain(result.timestamps),
        "min_bottom_do": _plain(result.min_bottom_do),
        "mean_surface_do": _plain(result.mean_surface_do),
        "hypoxic_volumes": _plain(result.hypoxic_volumes),
    }


@app.get("/api/simulations/{simulation_id}/spatial")
def get_spatial(
    simulation_id: str,
    hour: int = 5,
    field: str = "do",
    depth_layer: int = -1,
    contour_view: str = "vertical",
    y_slice: Optional[int] = None,
) -> Dict[str, Any]:
    simulation = _lookup(simulation_id)
    result: SimulationResult = simulation["result"]
    config: SimulationConfig = simulation["config"]
    hour = max(0, min(hour, len(result.timestamps) - 1))
    depth_layer = max(0, min(depth_layer, config.nz - 1))
    return {
        "hour": hour,
        "field": field,
        "depth_layer": depth_layer,
        "depth": float(result.z_coords[depth_layer]),
        "volume": _figure_json(InteractivePlotter.create_3d_volume_figure(result, hour, field, config.stocking_count)),
        "heatmap": _figure_json(InteractivePlotter.create_interactive_depth_heatmap(result, hour, depth_layer)),
        "contours": _figure_json(InteractivePlotter.create_contour_profiles(result, hour, contour_view, y_slice)),
        "contour_view": contour_view,
    }


@app.post("/api/simulations/{simulation_id}/optimizer")
def run_optimizer(simulation_id: str, stocking_counts: Optional[List[int]] = None) -> Dict[str, Any]:
    simulation = _lookup(simulation_id)
    weather: WeatherData24H = simulation["weather"]
    config: SimulationConfig = simulation["config"]
    counts = stocking_counts or [10000, 20000, 30000, 40000, 50000]
    optimizer = StockingOptimizer(config, weather.solar_irradiance, weather.air_temperature)
    results = optimizer.run_scenario_matrix(counts)
    return {"results": [_public_scenario(item) for item in results]}


@app.get("/api/simulations/{simulation_id}/report", response_class=HTMLResponse)
def get_report(simulation_id: str) -> str:
    simulation = _lookup(simulation_id)
    return FeasibilityReportGenerator.generate_html_report(
        config=simulation["config"],
        result=simulation["result"],
        report_data=simulation["report"],
        feed_type=simulation["feed_type"],
        location_label=simulation["weather"].location_name,
    )