"""Matplotlib Publication-Grade Contour Mapping for Pond Gradients.

Generates 2D vertical depth cross-sections (X-Z), horizontal benthic contour maps (X-Y),
and diurnal 24-hour time series with automated hypoxic zone warning contours.
"""

from typing import Optional, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from models.diffusion_engine import SimulationResult


class PondContourPlotter:
    """Creates Matplotlib publication-quality contour figures."""

    @staticmethod
    def plot_vertical_cross_section(
        result: SimulationResult,
        hour_idx: int = 5,
        y_idx: Optional[int] = None,
        hypoxia_threshold: float = 3.5,
    ) -> plt.Figure:
        """Plots X-Z depth cross-section comparing Temperature and DO gradients."""
        if y_idx is None:
            y_idx = len(result.y_coords) // 2

        # Extract 2D slices: shape (nx, nz)
        do_slice = result.do_grid[hour_idx, :, y_idx, :].T     # Shape: (nz, nx)
        temp_slice = result.temp_grid[hour_idx, :, y_idx, :].T # Shape: (nz, nx)

        x_grid, z_grid = np.meshgrid(result.x_coords, result.z_coords)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.2), dpi=150)
        fig.suptitle(
            f"Aquaculture Pond Vertical Cross-Section (X-Z Plane at Y = {result.y_coords[y_idx]:.1f}m) | Hour {hour_idx:02d}:00",
            fontsize=13,
            fontweight="bold",
            y=0.98,
        )

        # 1. Dissolved Oxygen Contour
        # Levels from 0 to 10 mg/L
        do_levels = np.linspace(0.5, 9.5, 19)
        cf1 = ax1.contourf(x_grid, z_grid, do_slice, levels=do_levels, cmap="viridis", extend="both")
        c1 = ax1.contour(x_grid, z_grid, do_slice, levels=do_levels, colors="white", alpha=0.3, linewidths=0.7)
        ax1.clabel(c1, inline=True, fontsize=8, fmt="%.1f")

        # Hypoxic threshold red contour line
        if np.any(do_slice < hypoxia_threshold):
            hypo_c = ax1.contour(
                x_grid, z_grid, do_slice, levels=[hypoxia_threshold], colors="#E53E3E", linewidths=2.5, linestyles="--"
            )
            ax1.clabel(hypo_c, inline=True, fontsize=9, fmt=f"Hypoxia ({hypoxia_threshold} mg/L)")

        cbar1 = fig.colorbar(cf1, ax=ax1, orientation="horizontal", pad=0.18, shrink=0.85)
        cbar1.set_label("Dissolved Oxygen (mg/L)", fontsize=10, fontweight="bold")
        ax1.set_title("Dissolved Oxygen (DO) Profile", fontsize=11, fontweight="bold")
        ax1.set_xlabel("Pond Length X (m)", fontsize=10)
        ax1.set_ylabel("Depth Z (m)", fontsize=10)
        ax1.invert_yaxis()  # Water surface is 0m at top, bottom depth is downwards
        ax1.grid(True, linestyle=":", alpha=0.5)

        # 2. Temperature Contour
        t_min = float(np.min(temp_slice)) - 0.5
        t_max = float(np.max(temp_slice)) + 0.5
        temp_levels = np.linspace(t_min, t_max, 15)
        cf2 = ax2.contourf(x_grid, z_grid, temp_slice, levels=temp_levels, cmap="plasma", extend="both")
        c2 = ax2.contour(x_grid, z_grid, temp_slice, levels=temp_levels, colors="black", alpha=0.3, linewidths=0.7)
        ax2.clabel(c2, inline=True, fontsize=8, fmt="%.1f")

        cbar2 = fig.colorbar(cf2, ax=ax2, orientation="horizontal", pad=0.18, shrink=0.85)
        cbar2.set_label("Temperature (°C)", fontsize=10, fontweight="bold")
        ax2.set_title("Thermal Stratification Profile", fontsize=11, fontweight="bold")
        ax2.set_xlabel("Pond Length X (m)", fontsize=10)
        ax2.set_ylabel("Depth Z (m)", fontsize=10)
        ax2.invert_yaxis()
        ax2.grid(True, linestyle=":", alpha=0.5)

        plt.tight_layout()
        return fig

    @staticmethod
    def plot_benthic_floor_contour(
        result: SimulationResult,
        hour_idx: int = 5,
        hypoxia_threshold: float = 3.5,
    ) -> plt.Figure:
        """Plots X-Y horizontal contour at the benthic floor (z = z_max) where shrimp dwell."""
        # Bottom slice: z = -1
        do_bottom = result.do_grid[hour_idx, :, :, -1]  # Shape: (nx, ny)
        temp_bottom = result.temp_grid[hour_idx, :, :, -1]

        x_grid, y_grid = np.meshgrid(result.x_coords, result.y_coords)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=150)
        fig.suptitle(
            f"Benthic Floor Habitat (Z = {result.z_coords[-1]:.1f}m Depth) | Hour {hour_idx:02d}:00",
            fontsize=13,
            fontweight="bold",
            y=0.98,
        )

        # 1. Benthic DO
        do_levels = np.linspace(max(0.5, float(np.min(do_bottom)) - 0.5), float(np.max(do_bottom)) + 0.5, 15)
        cf1 = ax1.contourf(x_grid, y_grid, do_bottom.T, levels=do_levels, cmap="YlGnBu", extend="both")
        c1 = ax1.contour(x_grid, y_grid, do_bottom.T, levels=do_levels, colors="black", alpha=0.3, linewidths=0.7)
        ax1.clabel(c1, inline=True, fontsize=8, fmt="%.1f")

        if np.any(do_bottom < hypoxia_threshold):
            hc = ax1.contour(
                x_grid, y_grid, do_bottom.T, levels=[hypoxia_threshold], colors="#E53E3E", linewidths=2.5, linestyles="--"
            )
            ax1.clabel(hc, inline=True, fontsize=9, fmt="Hypoxic Hazard")

        cbar1 = fig.colorbar(cf1, ax=ax1, orientation="horizontal", pad=0.18, shrink=0.85)
        cbar1.set_label("Bottom Benthic DO (mg/L)", fontsize=10, fontweight="bold")
        ax1.set_title("Penaeus vannamei Habitat DO", fontsize=11, fontweight="bold")
        ax1.set_xlabel("Pond Length X (m)", fontsize=10)
        ax1.set_ylabel("Pond Width Y (m)", fontsize=10)
        ax1.grid(True, linestyle=":", alpha=0.5)

        # 2. Benthic Temp
        t_levels = np.linspace(float(np.min(temp_bottom)) - 0.2, float(np.max(temp_bottom)) + 0.2, 12)
        cf2 = ax2.contourf(x_grid, y_grid, temp_bottom.T, levels=t_levels, cmap="coolwarm", extend="both")
        cbar2 = fig.colorbar(cf2, ax=ax2, orientation="horizontal", pad=0.18, shrink=0.85)
        cbar2.set_label("Bottom Temperature (°C)", fontsize=10, fontweight="bold")
        ax2.set_title("Benthic Temperature Distribution", fontsize=11, fontweight="bold")
        ax2.set_xlabel("Pond Length X (m)", fontsize=10)
        ax2.set_ylabel("Pond Width Y (m)", fontsize=10)
        ax2.grid(True, linestyle=":", alpha=0.5)

        plt.tight_layout()
        return fig

    @staticmethod
    def plot_diurnal_summary_timeseries(
        result: SimulationResult,
        hypoxia_threshold: float = 3.5,
    ) -> plt.Figure:
        """Plots 24-hour time series of Surface vs Bottom DO and Hypoxic Volume."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6.5), dpi=140, sharex=True)

        hours = result.timestamps

        # Subplot 1: DO comparison
        ax1.plot(hours, result.mean_surface_do, color="#3182CE", linewidth=2.4, label="Surface DO (Mean)")
        ax1.plot(hours, result.min_bottom_do, color="#E53E3E", linewidth=2.4, label="Bottom Benthic DO (Min)")
        ax1.axhline(hypoxia_threshold, color="#DD6B20", linestyle="--", linewidth=1.8, label=f"Hypoxic Limit ({hypoxia_threshold} mg/L)")
        ax1.axhline(2.0, color="#742A2A", linestyle=":", linewidth=1.8, label="Lethal Threshold (2.0 mg/L)")
        ax1.fill_between(hours, 0, hypoxia_threshold, color="#FED7D7", alpha=0.4, label="Hypoxia Risk Zone")

        ax1.set_ylabel("Dissolved Oxygen (mg/L)", fontsize=10, fontweight="bold")
        ax1.set_title("24-Hour Diurnal DO Dynamics across Pond Depths", fontsize=11, fontweight="bold")
        ax1.grid(True, linestyle=":", alpha=0.6)
        ax1.legend(loc="upper right", frameon=True, fontsize=8.5)
        ax1.set_ylim(bottom=0.0)

        # Subplot 2: Hypoxic Pond Volume Fraction %
        ax2.fill_between(hours, result.hypoxic_volumes, color="#FC8181", alpha=0.6, label="Hypoxic Pond Volume (< 3.0 mg/L)")
        ax2.plot(hours, result.hypoxic_volumes, color="#C53030", linewidth=2.0)
        ax2.set_xlabel("Time of Day (Hours 00:00 - 24:00)", fontsize=10, fontweight="bold")
        ax2.set_ylabel("Hypoxic Volume (%)", fontsize=10, fontweight="bold")
        ax2.set_title("Automated Hypoxic Spatial Volume Progression", fontsize=11, fontweight="bold")
        ax2.grid(True, linestyle=":", alpha=0.6)
        ax2.set_xlim(0, 24)
        ax2.set_xticks(np.arange(0, 25, 2))
        ax2.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
        ax2.legend(loc="upper right", frameon=True, fontsize=8.5)

        plt.tight_layout()
        return fig
