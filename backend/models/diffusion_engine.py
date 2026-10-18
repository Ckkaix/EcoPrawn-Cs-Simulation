"""3D Advection-Diffusion-Reaction PDE Engine for Aquaculture Ponds.

Solves the coupled 3D partial differential equations governing:
1. Water Temperature (T) diffusion and solar thermal stratification.
2. Dissolved Oxygen (DO) dynamics, benthic sediment oxygen demand,
   surface re-aeration, algal photosynthesis, and prawn/feed respiration.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class SimulationConfig:
    """Configuration parameters for 3D pond simulation."""
    # Pond Dimensions (meters)
    length: float = 20.0       # Pond X dimension (m)
    width: float = 20.0        # Pond Y dimension (m)
    depth: float = 1.5         # Pond Z depth (m)

    # Discretization Grid
    nx: int = 20               # X grid points
    ny: int = 20               # Y grid points
    nz: int = 10               # Z depth layers

    # Physical Properties
    diffusivity_t_h: float = 5.0e-5    # Horizontal thermal diffusivity (m^2/s)
    diffusivity_t_v: float = 3.0e-4    # Vertical thermal eddy diffusivity (m^2/s)
    diffusivity_do_h: float = 5.0e-5   # Horizontal DO diffusivity (m^2/s)
    diffusivity_do_v: float = 2.5e-4   # Vertical DO eddy diffusivity (m^2/s)
    light_extinction_k: float = 1.8    # Beer-Lambert light attenuation coefficient (1/m)
    heat_capacity: float = 4.184e6     # Volumetric heat capacity of water (J/(m^3 * K))

    # Re-aeration and Biochemical Constants
    surface_ka: float = 0.15           # Surface re-aeration exchange rate (1/hr)
    sod_rate: float = 0.035            # Sediment Oxygen Demand at 20°C (g O2/(m^2 * hr))
    algal_photo_max: float = 0.95      # Peak photosynthetic O2 production (mg/(L * hr))
    algal_resp_rate: float = 0.05      # Water column algal/microbial respiration (mg/(L * hr))

    # Prawn Stocking & Respiration Parameters
    stocking_count: int = 18000        # Desired shrimp stocking count (45/m² for 20x20m pond)
    individual_weight_g: float = 18.0  # Average weight per shrimp (grams)
    base_respiration_rate: float = 0.35# mg O2 / (g prawn * hr) at 28°C
    q10_respiration: float = 2.1       # Temperature coefficient for respiration

    # Feed Loading & Biological Oxygen Demand
    daily_feed_kg: float = 12.0        # Daily feed input (kg/day)
    feed_bod_factor: float = 0.12      # BOD oxygen demand factor (g O2 / g feed)
    feed_protein_ratio: float = 0.35   # Protein content ratio (0.35 ordinary, 0.42 fortified)

    # Aeration Control
    aeration_enabled: bool = False
    aeration_start_hour: int = 1       # Start hour (0-23)
    aeration_end_hour: int = 6         # End hour (0-23)
    aeration_boost_ka: float = 0.85    # Ka enhancement with mechanical aerators (1/hr)


@dataclass
class SimulationResult:
    """Holds time-series 3D grid outputs and summary statistics."""
    timestamps: np.ndarray             # Array of simulation hours [0, 1, ..., 24]
    x_coords: np.ndarray               # 1D coordinates along X (m)
    y_coords: np.ndarray               # 1D coordinates along Y (m)
    z_coords: np.ndarray               # 1D depth coordinates (m, 0 = surface, depth = bottom)
    temp_grid: np.ndarray              # 4D array: shape (hours, nx, ny, nz) in °C
    do_grid: np.ndarray                # 4D array: shape (hours, nx, ny, nz) in mg/L
    hypoxic_volumes: np.ndarray        # 1D array of hypoxic volume percentage over time (< 3.0 mg/L)
    min_bottom_do: np.ndarray          # 1D array of minimum bottom DO over time (mg/L)
    mean_surface_do: np.ndarray        # 1D array of mean surface DO over time (mg/L)
    hourly_solar: np.ndarray           # Hourly solar radiation used (W/m^2)
    hourly_air_temp: np.ndarray        # Hourly ambient air temp used (°C)


class Pond3DDiffusionSolver:
    """High-performance 3D finite-difference solver for thermal and DO diffusion."""

    def __init__(self, config: SimulationConfig):
        self.cfg = config
        self.dx = config.length / (config.nx - 1)
        self.dy = config.width / (config.ny - 1)
        self.dz = config.depth / (config.nz - 1)
        self.x = np.linspace(0, config.length, config.nx)
        self.y = np.linspace(0, config.width, config.ny)
        self.z = np.linspace(0, config.depth, config.nz)

        # Total pond water volume in cubic meters
        self.pond_volume_m3 = config.length * config.width * config.depth
        self.bottom_area_m2 = config.length * config.width

    @staticmethod
    def calculate_do_saturation(temp_c: np.ndarray, salinity_ppt: float = 15.0) -> np.ndarray:
        """Henry's law DO saturation (mg/L) as a function of temperature and salinity."""
        # Standard APHA formulation for aquatic water
        tk = temp_c + 273.15
        ln_do = (
            -139.34411
            + (1.575701e5 / tk)
            - (6.642308e7 / (tk**2))
            + (1.243800e10 / (tk**3))
            - (8.621949e11 / (tk**4))
        )
        do_fresh = np.exp(ln_do)
        # Salinity correction factor
        salinity_correction = np.exp(
            -salinity_ppt * (0.017674 - (10.754 / tk) + (2140.7 / (tk**2)))
        )
        return np.maximum(do_fresh * salinity_correction, 0.0)

    def _compute_laplacian_3d(self, field: np.ndarray, diff_h: float, diff_v: float) -> np.ndarray:
        """Computes anisotropic 3D Laplacian with zero-flux Neumann boundary conditions."""
        lap = np.zeros_like(field)

        # Interior X-diffusion
        lap[1:-1, :, :] += diff_h * (field[2:, :, :] - 2.0 * field[1:-1, :, :] + field[:-2, :, :]) / (self.dx**2)
        # Boundary X
        lap[0, :, :] += diff_h * 2.0 * (field[1, :, :] - field[0, :, :]) / (self.dx**2)
        lap[-1, :, :] += diff_h * 2.0 * (field[-2, :, :] - field[-1, :, :]) / (self.dx**2)

        # Interior Y-diffusion
        lap[:, 1:-1, :] += diff_h * (field[:, 2:, :] - 2.0 * field[:, 1:-1, :] + field[:, :-2, :]) / (self.dy**2)
        # Boundary Y
        lap[:, 0, :] += diff_h * 2.0 * (field[:, 1, :] - field[:, 0, :]) / (self.dy**2)
        lap[:, -1, :] += diff_h * 2.0 * (field[:, -2, :] - field[:, -1, :]) / (self.dy**2)

        # Interior Z-diffusion
        lap[:, :, 1:-1] += diff_v * (field[:, :, 2:] - 2.0 * field[:, :, 1:-1] + field[:, :, :-2]) / (self.dz**2)
        # Boundary Z
        lap[:, :, 0] += diff_v * 2.0 * (field[:, :, 1] - field[:, :, 0]) / (self.dz**2)
        lap[:, :, -1] += diff_v * 2.0 * (field[:, :, -2] - field[:, :, -1]) / (self.dz**2)

        return lap

    def solve(
        self,
        solar_irradiance: np.ndarray,
        air_temperature: np.ndarray,
        initial_temp: float = 28.0,
        initial_do: float = 6.2,
        dt_seconds: float = 30.0,
    ) -> SimulationResult:
        """Executes full 24-hour simulation across time steps.

        Args:
            solar_irradiance: 24-element array of hourly solar radiation (W/m^2).
            air_temperature: 24-element array of hourly air temperature (°C).
            initial_temp: Initial uniform water temperature (°C).
            initial_do: Initial uniform dissolved oxygen (mg/L).
            dt_seconds: Sub-step numerical time increment (seconds).

        Returns:
            SimulationResult containing 4D fields and summary metrics.
        """
        nx, ny, nz = self.cfg.nx, self.cfg.ny, self.cfg.nz
        hours_total = len(solar_irradiance)

        # State fields: shape (nx, ny, nz)
        temp_state = np.full((nx, ny, nz), initial_temp, dtype=np.float64)
        do_state = np.full((nx, ny, nz), initial_do, dtype=np.float64)

        # Precompute depth array for Beer-Lambert attenuation (shape: 1, 1, nz)
        z_3d = self.z.reshape((1, 1, nz))
        light_attenuation = np.exp(-self.cfg.light_extinction_k * z_3d)

        # Benthic prawn biomass distribution: concentrated in bottom layers (z >= 75% depth)
        shrimp_layer_mask = (z_3d >= 0.75 * self.cfg.depth).astype(np.float64)
        shrimp_layers_count = max(np.sum(shrimp_layer_mask[0, 0, :]), 1.0)
        volume_per_cell = self.dx * self.dy * self.dz

        # Total prawn biomass in grams
        total_biomass_g = self.cfg.stocking_count * self.cfg.individual_weight_g

        # Hourly recording buffers
        record_hours = hours_total + 1
        temp_history = np.zeros((record_hours, nx, ny, nz), dtype=np.float32)
        do_history = np.zeros((record_hours, nx, ny, nz), dtype=np.float32)
        hypoxic_volumes = np.zeros(record_hours, dtype=np.float32)
        min_bottom_do = np.zeros(record_hours, dtype=np.float32)
        mean_surface_do = np.zeros(record_hours, dtype=np.float32)

        def record_snapshot(idx: int):
            temp_history[idx] = temp_state
            do_history[idx] = do_state
            # Hypoxic threshold = 3.0 mg/L
            hypoxic_cells = np.sum(do_state < 3.0)
            hypoxic_volumes[idx] = (hypoxic_cells / (nx * ny * nz)) * 100.0
            min_bottom_do[idx] = float(np.min(do_state[:, :, -1]))
            mean_surface_do[idx] = float(np.mean(do_state[:, :, 0]))

        record_snapshot(0)

        # Sub-stepping per hour with CFL condition check
        # CFL condition: dt <= 0.4 / (2 * (diff_h/dx^2 + diff_h/dy^2 + diff_v/dz^2))
        max_v_diff_t = self.cfg.diffusivity_t_v * (3.0 if self.cfg.aeration_enabled else 1.0)
        max_v_diff_do = self.cfg.diffusivity_do_v * (4.0 if self.cfg.aeration_enabled else 1.0)
        max_diff_v = max(max_v_diff_t, max_v_diff_do)
        max_diff_h = max(self.cfg.diffusivity_t_h, self.cfg.diffusivity_do_h)

        diffusion_rate_sum = 2.0 * (
            (max_diff_h / (self.dx**2))
            + (max_diff_h / (self.dy**2))
            + (max_diff_v / (self.dz**2))
        )
        cfl_dt = 0.45 / max(diffusion_rate_sum, 1e-6)
        actual_dt = min(dt_seconds, cfl_dt, 60.0)
        substeps_per_hour = max(int(np.ceil(3600.0 / actual_dt)), 60)
        step_dt = 3600.0 / substeps_per_hour

        for h in range(hours_total):
            i_solar = float(solar_irradiance[h])
            t_air = float(air_temperature[h])

            # Determine aerator status for this hour
            is_aerating = (
                self.cfg.aeration_enabled
                and (self.cfg.aeration_start_hour <= h <= self.cfg.aeration_end_hour)
            )
            current_ka = (
                (self.cfg.surface_ka + self.cfg.aeration_boost_ka)
                if is_aerating
                else self.cfg.surface_ka
            )
            # Eddy diffusivity increases during mechanical aeration due to circulation
            v_diff_t = self.cfg.diffusivity_t_v * (2.5 if is_aerating else 1.0)
            v_diff_do = self.cfg.diffusivity_do_v * (3.0 if is_aerating else 1.0)

            for _ in range(substeps_per_hour):
                # ----------------- 1. Thermal Dynamics -----------------
                lap_temp = self._compute_laplacian_3d(temp_state, self.cfg.diffusivity_t_h, v_diff_t)

                # Solar radiative heating source term (Beer-Lambert law)
                # q_solar in W/m^3 -> divided by rho*cp yields °C/s
                solar_heating_rate = (
                    self.cfg.light_extinction_k * i_solar * light_attenuation
                ) / self.cfg.heat_capacity

                # Surface atmospheric heat exchange flux (W/m^2 converted across surface cell dz)
                # Convective heat transfer coefficient h_c ~ 15 W/(m^2 * K)
                surface_heat_flux = 15.0 * (t_air - temp_state[:, :, 0]) / (self.cfg.heat_capacity * self.dz)

                d_temp = lap_temp + solar_heating_rate
                d_temp[:, :, 0] += surface_heat_flux

                temp_state += d_temp * step_dt
                temp_state = np.clip(temp_state, 15.0, 42.0)

                # ----------------- 2. Dissolved Oxygen Dynamics -----------------
                lap_do = self._compute_laplacian_3d(do_state, self.cfg.diffusivity_do_h, v_diff_do)

                # Local DO Saturation
                sat_do = self.calculate_do_saturation(temp_state)

                # Surface Atmospheric Re-aeration (mg/L per second)
                # Reaeration applies to top layer (z=0)
                reaeration_rate = (current_ka / 3600.0) * (sat_do[:, :, 0] - do_state[:, :, 0])

                # Photosynthetic O2 generation (daylight hours only, scaled by solar intensity)
                # Normalized by solar peak ~ 900 W/m^2
                solar_factor = min(i_solar / 850.0, 1.2) if i_solar > 10.0 else 0.0
                photosynthesis = (
                    (self.cfg.algal_photo_max / 3600.0)
                    * solar_factor
                    * light_attenuation
                )

                # Water Column Algal/Microbial Respiration
                water_respiration = self.cfg.algal_resp_rate / 3600.0

                # Benthic Sediment Oxygen Demand (applied to bottom layer z=-1)
                # Converted from g/(m^2*hr) -> mg/(L*s) in bottom cell
                sod_bottom = (
                    (self.cfg.sod_rate * 1000.0)  # g to mg
                    / (self.dz * 1000.0 * 3600.0) # m^3 to L and hr to sec
                ) * (1.065 ** (temp_state[:, :, -1] - 20.0))

                # Penaeus vannamei Prawn Respiration (concentrated in benthic layers)
                # Respiration rate Q10 temperature effect
                q10_factor = self.cfg.q10_respiration ** ((temp_state - 28.0) / 10.0)
                # Monod DO limitation (shrimp respiration slows if DO collapses)
                do_limitation = np.clip(do_state / (1.5 + do_state), 0.0, 1.0)

                # Total prawn oxygen demand per cell (mg/L/s)
                # Biomass distributed evenly across bottom layers
                biomass_per_benthic_cell_g = (
                    (total_biomass_g / (nx * ny * shrimp_layers_count))
                    * shrimp_layer_mask
                )
                prawn_resp_rate = (
                    (self.cfg.base_respiration_rate * biomass_per_benthic_cell_g)
                    / (volume_per_cell * 1000.0 * 3600.0) # per L per sec
                ) * q10_factor * do_limitation

                # Unconsumed Feed Decomposition BOD
                # Distributed to benthic floor
                # Daily feed divided by 24h, factor multiplied by protein multiplier
                protein_mult = 1.0 + (self.cfg.feed_protein_ratio - 0.35) * 1.5
                feed_bod_hourly_mg = (
                    (self.cfg.daily_feed_kg * 1e6 / 24.0)
                    * self.cfg.feed_bod_factor
                    * protein_mult
                )
                feed_bod_per_cell = (
                    (feed_bod_hourly_mg / (nx * ny * shrimp_layers_count))
                    / (volume_per_cell * 1000.0 * 3600.0)
                ) * shrimp_layer_mask

                # Combine reaction terms
                d_do = lap_do + photosynthesis - water_respiration - prawn_resp_rate - feed_bod_per_cell
                d_do[:, :, 0] += reaeration_rate
                d_do[:, :, -1] -= sod_bottom

                do_state += d_do * step_dt
                do_state = np.clip(do_state, 0.05, 25.0)

            record_snapshot(h + 1)

        timestamps = np.arange(record_hours)
        return SimulationResult(
            timestamps=timestamps,
            x_coords=self.x,
            y_coords=self.y,
            z_coords=self.z,
            temp_grid=temp_history,
            do_grid=do_history,
            hypoxic_volumes=hypoxic_volumes,
            min_bottom_do=min_bottom_do,
            mean_surface_do=mean_surface_do,
            hourly_solar=np.array(solar_irradiance),
            hourly_air_temp=np.array(air_temperature),
        )
