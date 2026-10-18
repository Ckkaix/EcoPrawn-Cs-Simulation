"""Environmental Weather and IoT API Client.

Integrates with Open-Meteo for regional environmental solar/temperature data
and supports custom IoT REST endpoints (ThingSpeak / JSON sensors) with robust
fallback mechanisms.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import requests


@dataclass
class WeatherData24H:
    source_name: str
    location_name: str
    latitude: float
    longitude: float
    solar_irradiance: np.ndarray      # 24 elements in W/m^2
    air_temperature: np.ndarray       # 24 elements in °C
    wind_speed: np.ndarray            # 24 elements in m/s
    initial_water_temp_c: float       # Ingested or estimated baseline water temp
    initial_do_mg_l: float            # Ingested or estimated baseline DO
    is_live_api: bool


class EnvironmentalAPIClient:
    """Fetches real-time environmental data or retrieves from IoT sensor endpoints."""

    DEFAULT_CALOOCAN_LAT = 14.7565
    DEFAULT_CALOOCAN_LON = 121.0441

    def __init__(self, timeout_seconds: int = 5):
        self.timeout = timeout_seconds

    def fetch_open_meteo(
        self,
        lat: float = DEFAULT_CALOOCAN_LAT,
        lon: float = DEFAULT_CALOOCAN_LON,
        location_label: str = "Caloocan City, Metro Manila",
    ) -> Optional[WeatherData24H]:
        """Fetches 24-hour hourly forecast from Open-Meteo API."""
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,direct_normal_irradiance,shortwave_radiation,wind_speed_10m"
            "&timezone=Asia%2FManila&forecast_days=1"
        )
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                hourly = data.get("hourly", {})
                temps = np.array(hourly.get("temperature_2m", [])[:24], dtype=np.float64)
                solar = np.array(hourly.get("shortwave_radiation", [])[:24], dtype=np.float64)
                wind = np.array(hourly.get("wind_speed_10m", [])[:24], dtype=np.float64)

                if len(temps) == 24 and len(solar) == 24:
                    # Baseline water temperature closely follows early morning ambient air (~06:00)
                    baseline_water_temp = float(temps[6]) if len(temps) > 6 else 28.0
                    # Tropical aquaculture pond morning DO typically around 5.5 - 6.5 mg/L
                    baseline_do = 6.2

                    return WeatherData24H(
                        source_name="Open-Meteo Environmental API (Live)",
                        location_name=location_label,
                        latitude=lat,
                        longitude=lon,
                        solar_irradiance=np.maximum(solar, 0.0),
                        air_temperature=temps,
                        wind_speed=wind if len(wind) == 24 else np.full(24, 2.5),
                        initial_water_temp_c=baseline_water_temp,
                        initial_do_mg_l=baseline_do,
                        is_live_api=True,
                    )
        except Exception:
            pass
        return None

    def fetch_iot_rest_endpoint(
        self,
        endpoint_url: str,
        api_key: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetches latest telemetry reading from a custom IoT REST endpoint."""
        headers = {}
        if api_key:
            headers["X-API-KEY"] = api_key

        try:
            resp = requests.get(endpoint_url, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None
