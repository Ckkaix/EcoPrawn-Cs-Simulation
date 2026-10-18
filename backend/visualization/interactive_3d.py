"""Plotly Interactive 3D and 2D Visualizations for EcoPrawn.

Provides rotatable 3D volume/isosurface visualizations, interactive depth slice
heatmaps, and dynamic diurnal time series for Streamlit dashboards.
"""

from typing import Optional
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from models.diffusion_engine import SimulationResult


class InteractivePlotter:
    """Creates rich interactive Plotly figures."""

    @staticmethod
    def create_contour_profiles(
        result: SimulationResult,
        hour_idx: int = 5,
        orientation: str = "vertical",
        y_slice_idx: Optional[int] = None,
    ) -> go.Figure:
        """Creates paired DO and temperature contour profiles."""
        if orientation == "benthic":
            do_values = result.do_grid[hour_idx, :, :, -1].T
            temp_values = result.temp_grid[hour_idx, :, :, -1].T
            x_values, y_values = result.x_coords, result.y_coords
            x_title, y_title = "Pond Length X (m)", "Pond Width Y (m)"
            title = f"Benthic Floor Habitat (Z = {result.z_coords[-1]:.1f}m Depth) | Hour {hour_idx:02d}:00"
        else:
            slice_idx = len(result.y_coords) // 2 if y_slice_idx is None else y_slice_idx
            slice_idx = max(0, min(slice_idx, len(result.y_coords) - 1))
            do_values = result.do_grid[hour_idx, :, slice_idx, :].T
            temp_values = result.temp_grid[hour_idx, :, slice_idx, :].T
            x_values, y_values = result.x_coords, result.z_coords
            x_title, y_title = "Pond Length X (m)", "Depth Z (m)"
            title = (
                f"Aquaculture Pond Vertical Cross-Section (X-Z Plane at Y = {result.y_coords[slice_idx]:.1f}m)"
                f" | Hour {hour_idx:02d}:00"
            )

        figure = make_subplots(rows=1, cols=2, subplot_titles=("Dissolved Oxygen (DO) Profile", "Thermal Stratification Profile"))
        do_min = 0.5
        do_max = 9.5
        figure.add_trace(
            go.Contour(
                x=x_values, y=y_values, z=do_values, colorscale="Viridis",
                zmin=do_min, zmax=do_max,
                colorbar=dict(title="Dissolved Oxygen (mg/L)", x=0.45),
                contours=dict(start=do_min, end=do_max, size=0.5, showlabels=True),
                hovertemplate="X: %{x:.1f}m<br>Depth/Width: %{y:.2f}m<br>DO: %{z:.2f} mg/L<extra></extra>",
            ),
            row=1, col=1,
        )
        figure.add_trace(
            go.Contour(
                x=x_values, y=y_values, z=do_values, contours=dict(start=3.5, end=3.5, size=1),
                showscale=False, line=dict(color="#E53E3E", width=3),
                hoverinfo="skip", name="Hypoxia threshold (3.5 mg/L)",
            ),
            row=1, col=1,
        )
        figure.add_trace(
            go.Contour(
                x=x_values, y=y_values, z=temp_values, colorscale="Plasma",
                colorbar=dict(title="Temperature (°C)", x=1.02), contours=dict(showlabels=True),
                hovertemplate="X: %{x:.1f}m<br>Depth/Width: %{y:.2f}m<br>Temperature: %{z:.2f} °C<extra></extra>",
            ),
            row=1, col=2,
        )
        figure.update_xaxes(title_text=x_title, row=1, col=1)
        figure.update_xaxes(title_text=x_title, row=1, col=2)
        figure.update_yaxes(title_text=y_title, autorange="reversed" if orientation != "benthic" else True, row=1, col=1)
        figure.update_yaxes(title_text=y_title, autorange="reversed" if orientation != "benthic" else True, row=1, col=2)
        figure.update_layout(title=title, height=520, margin=dict(l=35, r=35, t=75, b=35))
        return figure

    @staticmethod
    def create_3d_volume_figure(
        result: SimulationResult,
        hour_idx: int = 5,
        target_field: str = "do",
        stocking_count: int = 0,
    ) -> go.Figure:
        """Generates a rotatable 3D water-quality field with representative shrimp."""
        nx = len(result.x_coords)
        ny = len(result.y_coords)
        nz = len(result.z_coords)

        # Build coordinate mesh
        # Meshgrid indexing: 'ij' for matching array shapes (nx, ny, nz)
        x_3d, y_3d, z_3d = np.meshgrid(result.x_coords, result.y_coords, result.z_coords, indexing="ij")

        if target_field == "do":
            values = result.do_grid[hour_idx]  # Shape: (nx, ny, nz)
            val_min = 1.0
            val_max = 8.5
            colorscale = "Viridis"
            unit = "mg/L"
            title_text = f"3D Dissolved Oxygen (DO) Spatial Field | Hour {hour_idx:02d}:00"
            isomin = 1.5
            isomax = 7.5
        else:
            values = result.temp_grid[hour_idx]
            val_min = float(np.min(values))
            val_max = float(np.max(values))
            colorscale = "Plasma"
            unit = "°C"
            title_text = f"3D Thermal Gradient Spatial Field | Hour {hour_idx:02d}:00"
            isomin = val_min
            isomax = val_max

        # Flatten arrays for Plotly 3D Isosurface
        x_flat = x_3d.flatten()
        y_flat = y_3d.flatten()
        z_flat = z_3d.flatten()
        val_flat = values.flatten()

        fig = go.Figure(
            data=go.Isosurface(
                x=x_flat,
                y=y_flat,
                z=z_flat,
                value=val_flat,
                isomin=isomin,
                isomax=isomax,
                surface_count=6,
                colorscale=colorscale,
                cmin=val_min,
                cmax=val_max,
                colorbar=dict(
                    title=f"{target_field.upper()} ({unit})",
                    thickness=16,
                    len=0.7,
                    x=0.93,
                    xanchor="left",
                    xpad=4,
                    y=0.5,
                    yanchor="middle",
                ),
                caps=dict(x_show=False, y_show=False, z_show=False),
                opacity=0.65,
                slices_z=dict(show=True, locations=[float(result.z_coords[-1])]),  # Highlight bottom
                hovertemplate="X: %{x:.1f}m<br>Y: %{y:.1f}m<br>Depth: %{z:.2f}m<br>Val: %{value:.2f} " + unit + "<extra></extra>",
            )
        )

        # Show the pond geometry as a transparent reference around the simulated field.
        pond_x = [result.x_coords[0], result.x_coords[-1]]
        pond_y = [result.y_coords[0], result.y_coords[-1]]
        pond_z = [result.z_coords[0], result.z_coords[-1]]
        outline_x = [
            pond_x[0], pond_x[1], pond_x[1], pond_x[0], pond_x[0], None,
            pond_x[0], pond_x[1], pond_x[1], pond_x[0], pond_x[0], None,
            pond_x[0], pond_x[0], None, pond_x[1], pond_x[1], None,
            pond_x[1], pond_x[1], None, pond_x[0], pond_x[0],
        ]
        outline_y = [
            pond_y[0], pond_y[0], pond_y[1], pond_y[1], pond_y[0], None,
            pond_y[0], pond_y[0], pond_y[1], pond_y[1], pond_y[0], None,
            pond_y[0], pond_y[0], None, pond_y[0], pond_y[0], None,
            pond_y[1], pond_y[1], None, pond_y[1], pond_y[1],
        ]
        outline_z = [
            pond_z[0], pond_z[0], pond_z[0], pond_z[0], pond_z[0], None,
            pond_z[1], pond_z[1], pond_z[1], pond_z[1], pond_z[1], None,
            pond_z[0], pond_z[1], None, pond_z[0], pond_z[1], None,
            pond_z[0], pond_z[1], None, pond_z[0], pond_z[1],
        ]
        fig.add_trace(
            go.Scatter3d(
                x=outline_x,
                y=outline_y,
                z=outline_z,
                mode="lines",
                name="Pond boundary",
                line=dict(color="#0F766E", width=5),
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Surface(
                x=np.array([[pond_x[0], pond_x[1]], [pond_x[0], pond_x[1]]]),
                y=np.array([[pond_y[0], pond_y[0]], [pond_y[1], pond_y[1]]]),
                z=np.full((2, 2), pond_z[0]),
                surfacecolor=np.zeros((2, 2)),
                colorscale=[[0, "#7DD3FC"], [1, "#7DD3FC"]],
                opacity=0.16,
                showscale=False,
                name="Pond water surface",
                hoverinfo="skip",
            )
        )

        if stocking_count > 0:
            representative_count = min(stocking_count, 120)
            rng = np.random.default_rng(42)
            shrimp_x = rng.uniform(pond_x[0], pond_x[1], representative_count)
            shrimp_y = rng.uniform(pond_y[0], pond_y[1], representative_count)
            shrimp_z = rng.uniform(
                result.z_coords[max(0, int(0.75 * (nz - 1)))],
                pond_z[1],
                representative_count,
            )
            shrimp_line_x: list[float | None] = []
            shrimp_line_y: list[float | None] = []
            shrimp_line_z: list[float | None] = []
            shrimp_joint_x: list[float] = []
            shrimp_joint_y: list[float] = []
            shrimp_joint_z: list[float] = []

            def add_segment(
                points: list[tuple[float, float, float]],
                origin_x: float,
                origin_y: float,
                origin_z: float,
                angle: float,
            ) -> None:
                cos_angle, sin_angle = np.cos(angle), np.sin(angle)
                for local_x, local_y, local_z in points:
                    shrimp_line_x.append(origin_x + local_x * cos_angle - local_y * sin_angle)
                    shrimp_line_y.append(origin_y + local_x * sin_angle + local_y * cos_angle)
                    shrimp_line_z.append(origin_z + local_z)
                shrimp_line_x.append(None)
                shrimp_line_y.append(None)
                shrimp_line_z.append(None)

            for x, y, z in zip(shrimp_x, shrimp_y, shrimp_z):
                angle = float(rng.uniform(0.0, 2.0 * np.pi))
                body = [
                    (0.28, 0.00, 0.00), (0.19, 0.09, 0.015), (0.19, -0.09, 0.015),
                    (0.08, 0.13, 0.025), (0.08, -0.13, 0.025),
                    (-0.06, 0.11, 0.02), (-0.06, -0.11, 0.02),
                    (-0.19, 0.07, 0.01), (-0.19, -0.07, 0.01),
                    (-0.30, 0.00, 0.00),
                ]
                add_segment(body, x, y, z, angle)
                add_segment([(0.30, 0.00, 0.0), (0.42, 0.09, 0.015), (0.53, 0.14, 0.02)], x, y, z, angle)
                add_segment([(0.30, 0.00, 0.0), (0.42, -0.09, 0.015), (0.53, -0.14, 0.02)], x, y, z, angle)
                add_segment([(-0.28, 0.00, 0.0), (-0.43, 0.12, 0.02), (-0.43, -0.12, 0.02)], x, y, z, angle)
                add_segment([(0.16, 0.07, -0.02), (0.04, 0.20, -0.035)], x, y, z, angle)
                add_segment([(0.16, -0.07, -0.02), (0.04, -0.20, -0.035)], x, y, z, angle)
                add_segment([(0.02, 0.09, -0.02), (-0.10, 0.19, -0.04)], x, y, z, angle)
                add_segment([(0.02, -0.09, -0.02), (-0.10, -0.19, -0.04)], x, y, z, angle)
                for local_x, local_y in [(0.28, 0.0), (0.08, 0.0), (-0.10, 0.0), (-0.25, 0.0)]:
                    cos_angle, sin_angle = np.cos(angle), np.sin(angle)
                    shrimp_joint_x.append(x + local_x * cos_angle - local_y * sin_angle)
                    shrimp_joint_y.append(y + local_x * sin_angle + local_y * cos_angle)
                    shrimp_joint_z.append(z + 0.02)
            fig.add_trace(
                go.Scatter3d(
                    x=shrimp_line_x,
                    y=shrimp_line_y,
                    z=shrimp_line_z,
                    mode="lines",
                    name=f"Shrimp (representative {representative_count:,} of {stocking_count:,})",
                    line=dict(color="#F97316", width=5),
                    hoverinfo="skip",
                )
            )
            fig.add_trace(
                go.Scatter3d(
                    x=shrimp_joint_x,
                    y=shrimp_joint_y,
                    z=shrimp_joint_z,
                    mode="markers",
                    name="Shrimp body segments",
                    marker=dict(size=4, color="#FDBA74", opacity=0.95),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        fig.update_layout(
            title=dict(text=title_text, font=dict(size=15, color="#2D3748")),
            scene=dict(
                xaxis_title="Pond Length X (m)",
                yaxis_title="Pond Width Y (m)",
                zaxis_title="Depth Z (m)",
                domain=dict(x=[0.0, 0.82], y=[0.0, 1.0]),
                zaxis=dict(autorange="reversed"),  # Surface at top, bottom downwards
                aspectmode="manual",
                aspectratio=dict(x=1.2, y=1.2, z=0.5),
            ),
            margin=dict(l=10, r=10, t=45, b=10),
            height=540,
            showlegend=False,
        )

        return fig

    @staticmethod
    def create_interactive_depth_heatmap(
        result: SimulationResult,
        hour_idx: int = 5,
        depth_layer_idx: int = -1,
    ) -> go.Figure:
        """Creates interactive horizontal 2D heatmap with hover tooltips."""
        do_slice = result.do_grid[hour_idx, :, :, depth_layer_idx]
        temp_slice = result.temp_grid[hour_idx, :, :, depth_layer_idx]
        z_depth = result.z_coords[depth_layer_idx]

        fig = go.Figure(
            data=go.Heatmap(
                x=result.x_coords,
                y=result.y_coords,
                z=do_slice.T,
                colorscale="YlGnBu",
                colorbar=dict(title="DO (mg/L)"),
                customdata=temp_slice.T,
                hovertemplate="<b>X</b>: %{x:.1f}m<br><b>Y</b>: %{y:.1f}m<br><b>DO</b>: %{z:.2f} mg/L<br><b>Temp</b>: %{customdata:.2f} °C<extra></extra>",
            )
        )

        fig.update_layout(
            title=f"Horizontal DO Heatmap (Depth Z = {z_depth:.2f}m) | Hour {hour_idx:02d}:00",
            xaxis_title="Pond Length X (m)",
            yaxis_title="Pond Width Y (m)",
            height=430,
            margin=dict(l=30, r=30, t=50, b=30),
        )
        return fig

    @staticmethod
    def create_interactive_diurnal_chart(
        result: SimulationResult,
        hypoxia_threshold: float = 3.5,
    ) -> go.Figure:
        """Creates interactive multi-line chart for 24-hr progression."""
        hours = result.timestamps

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.12,
            subplot_titles=("Surface vs Bottom Dissolved Oxygen (DO)", "Pond Hypoxic Volume Fraction (%)"),
        )

        # Surface DO
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=result.mean_surface_do,
                mode="lines+markers",
                name="Surface DO (Mean)",
                line=dict(color="#3182CE", width=3),
            ),
            row=1,
            col=1,
        )

        # Bottom DO
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=result.min_bottom_do,
                mode="lines+markers",
                name="Bottom Benthic DO (Min)",
                line=dict(color="#E53E3E", width=3),
            ),
            row=1,
            col=1,
        )

        # Hypoxia threshold line
        fig.add_trace(
            go.Scatter(
                x=[0, 24],
                y=[hypoxia_threshold, hypoxia_threshold],
                mode="lines",
                name=f"Hypoxic Limit ({hypoxia_threshold} mg/L)",
                line=dict(color="#DD6B20", dash="dash", width=2),
            ),
            row=1,
            col=1,
        )

        # Lethal threshold line
        fig.add_trace(
            go.Scatter(
                x=[0, 24],
                y=[2.0, 2.0],
                mode="lines",
                name="Lethal Threshold (2.0 mg/L)",
                line=dict(color="#742A2A", dash="dot", width=2),
            ),
            row=1,
            col=1,
        )

        # Hypoxic volume trace
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=result.hypoxic_volumes,
                mode="lines",
                fill="tozeroy",
                name="Hypoxic Volume % (< 3.0 mg/L)",
                line=dict(color="#E53E3E", width=2),
                fillcolor="rgba(229, 62, 62, 0.25)",
            ),
            row=2,
            col=1,
        )

        fig.update_xaxes(
            title_text="Time of Day (Hours 00:00 - 24:00)",
            tickmode="linear",
            tick0=0,
            dtick=2,
            row=2,
            col=1,
        )
        fig.update_yaxes(title_text="DO (mg/L)", row=1, col=1)
        fig.update_yaxes(title_text="Volume (%)", row=2, col=1)

        fig.update_layout(
            height=580,
            margin=dict(l=30, r=30, t=50, b=30),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        return fig
