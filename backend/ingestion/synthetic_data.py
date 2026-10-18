"""Synthetic Diurnal Environmental Generator.

Generates physics-consistent 24-hour solar radiation, ambient air temperature,
and wind speed curves for tropical aquaculture ponds (Caloocan / Philippine climate)
when live API is offline or during controlled computational experiments.
"""

from typing import Tuple
import numpy as np

from .api_client import WeatherData24H


class SyntheticDataGenerator:
    """Generates realistic diurnal environmental curves."""

    @staticmethod
    def generate_diurnal_weather(
        weather_type: str = "Sunny / Clear Skies",
        base_temp_c: float = 29.5,
        temp_amplitude_c: float = 4.2,
        peak_solar_w_m2: float = 880.0,
        cloud_factor: float = 0.0,
    ) -> WeatherData24H:
        """Generates realistic 24-hour diurnal curves."""
        hours = np.arange(24)

        # Diurnal air temperature model: minimum at 05:00, maximum at 14:00
        # Phase shift: (hour - 9) * pi / 12 so min is at 05:00 and max is at 14:00
        temp_cycle = base_temp_c + temp_amplitude_c * np.sin((hours - 8.5) * np.pi / 12.0)

        # Diurnal solar radiation model: active between 06:00 and 18:00
        solar = np.zeros(24, dtype=np.float64)
        for h in range(6, 19):
            # Half-sine bell curve between sunrise (06:00) and sunset (18:00)
            angle = (h - 6.0) * np.pi / 12.0
            solar[h] = peak_solar_w_m2 * np.sin(angle)

        if weather_type == "Overcast / Rainy":
            solar *= 0.35
            temp_cycle -= 3.0
        elif weather_type == "Intermittent Clouds":
            solar *= (1.0 - 0.35 * np.sin(hours * 1.5) ** 2)

        # Apply random micro-fluctuations for realistic sensor appearance
        np.random.seed(42)
        noise_temp = np.random.normal(0, 0.2, 24)
        temps = np.round(temp_cycle + noise_temp, 2)
        solar = np.maximum(np.round(solar, 1), 0.0)

        wind = np.full(24, 2.8) + np.random.normal(0, 0.4, 24)
        wind = np.maximum(wind, 0.5)

        return WeatherData24H(
            source_name="Synthetic Physics-Informed Generator (Caloocan Baseline)",
            location_name="Caloocan City Pond Simulation Site",
            latitude=14.7565,
            longitude=121.0441,
            solar_irradiance=solar,
            air_temperature=temps,
            wind_speed=wind,
            initial_water_temp_c=float(temps[6]),
            initial_do_mg_l=6.2,
            is_live_api=False,
        )
