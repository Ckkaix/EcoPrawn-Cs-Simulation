"""3D Low-Poly Shrimp mesh loader and Plotly trace builder.

Model Attribution:
    "Shrimp [Low Poly]" (https://sketchfab.com/3d-models/shrimp-low-poly-652650059ff949b39bbed3bfc34d5e87)
    by Fecalis (https://sketchfab.com/Fecalis), licensed under CC Attribution 4.0 (CC BY 4.0).
"""

from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np
import plotly.graph_objects as go


ASSET_PATH = Path(__file__).with_name("shrimp_low_poly.npz")
MODEL_ATTRIBUTION = (
    '3D Model: "Shrimp [Low Poly]" by Fecalis '
    "(https://sketchfab.com/3d-models/shrimp-low-poly-652650059ff949b39bbed3bfc34d5e87) · CC BY 4.0"
)


@lru_cache(maxsize=1)
def load_shrimp_template() -> dict[str, object]:
    """Loads and caches the normalized low-poly shrimp mesh and color palette."""
    with np.load(ASSET_PATH) as data:
        vertices = np.array(data["vertices"], dtype=np.float32)
        triangles = np.array(data["triangles"], dtype=np.uint16)
        cell_intensity = np.array(data["cell_intensity"], dtype=np.uint8)
        palette_rgb = np.array(data["palette_rgb"], dtype=np.uint8)
        face_rgb = np.array(data["face_rgb"], dtype=np.uint8)

    n_colors = max(1, len(palette_rgb) - 1)
    colorscale = [
        [idx / n_colors, f"#{int(r):02x}{int(g):02x}{int(b):02x}"]
        for idx, (r, g, b) in enumerate(palette_rgb)
    ]

    return {
        "vertices": vertices,
        "triangles": triangles,
        "cell_intensity": cell_intensity,
        "colorscale": colorscale,
        "max_palette_index": len(palette_rgb) - 1,
        "face_rgb": face_rgb,
    }


def build_shrimp_mesh3d_trace(
    pond_x: Sequence[float],
    pond_y: Sequence[float],
    pond_z: Sequence[float],
    benthic_z_min: float,
    stocking_count: int,
    max_representative: int = 65,
    seed: int = 42,
    scene_aspect: tuple[float, float, float] = (1.2, 1.2, 0.5),
) -> go.Mesh3d:
    """Builds a batched Plotly Mesh3d trace of low-poly shrimp in the benthic zone.

    Compensates for the pond scene's manual aspect ratio and reversed Z depth axis
    so each shrimp preserves the true 3D proportions of the Fecalis low-poly model.
    """
    template = load_shrimp_template()
    vertices: np.ndarray = template["vertices"]  # type: ignore[assignment]
    triangles: np.ndarray = template["triangles"]  # type: ignore[assignment]
    cell_intensity: np.ndarray = template["cell_intensity"]  # type: ignore[assignment]
    colorscale: list[list[object]] = template["colorscale"]  # type: ignore[assignment]
    max_palette_index: int = template["max_palette_index"]  # type: ignore[assignment]

    # Ensure vertex count fits within uint16 index range (< 65,535)
    max_safe_instances = min(max_representative, 65000 // len(vertices))
    
    # Scale representative shrimp count dynamically across stocking range (1 to 200,000+)
    # 0 -> 0, 1,000 -> ~6, 10,000 -> ~18, 18,000 -> ~25, 50,000 -> ~42, 100,000+ -> up to max_safe_instances
    if stocking_count <= 0:
        representative_count = 0
    elif stocking_count <= 25:
        representative_count = min(int(stocking_count), max_safe_instances)
    else:
        # Scale smoothly relative to reference stocking count of 18,000 (typical 45 shrimp/m² in 20x20m pond)
        scaled_count = int(np.round(25.0 * np.sqrt(float(stocking_count) / 18000.0)))
        representative_count = max(1, min(scaled_count, max_safe_instances))

    x_span = float(pond_x[1] - pond_x[0])
    y_span = float(pond_y[1] - pond_y[0])
    z_span = float(pond_z[1] - pond_z[0])
    horiz_span = min(x_span, y_span)

    # Scale shrimp relative to pond dimensions and compensate for visual box aspect ratio
    base_xy_scale = np.float32(0.052 * horiz_span)
    aspect_xy = 0.5 * (scene_aspect[0] + scene_aspect[1])
    aspect_z = scene_aspect[2]
    z_compensation = (z_span / aspect_z) / (horiz_span / aspect_xy)
    base_z_scale = np.float32(float(base_xy_scale) * z_compensation)

    local_forward = vertices[:, 0]
    local_side = vertices[:, 1]
    local_up = vertices[:, 2]

    margin_x = min(0.2 * x_span, float(base_xy_scale) * 0.85)
    margin_y = min(0.2 * y_span, float(base_xy_scale) * 0.85)

    # Keep vertical bounds strictly inside the benthic layer above the pond floor (pond_z[1])
    up_max = float(local_up.max()) * float(base_z_scale)
    down_max = float(-local_up.min()) * float(base_z_scale)
    z_upper_limit = max(float(pond_z[0]) + up_max, float(benthic_z_min))
    z_lower_limit = float(pond_z[1]) - down_max * 1.02
    if z_upper_limit >= z_lower_limit:
        z_center = float(pond_z[1]) - down_max * 1.05
        z_upper_limit = max(float(pond_z[0]) + up_max, z_center - 0.04 * z_span)
        z_lower_limit = max(z_upper_limit + 1e-3, z_center)

    rng = np.random.default_rng(seed)
    origin_x = rng.uniform(float(pond_x[0]) + margin_x, float(pond_x[1]) - margin_x, representative_count).astype(np.float32)
    origin_y = rng.uniform(float(pond_y[0]) + margin_y, float(pond_y[1]) - margin_y, representative_count).astype(np.float32)
    origin_z = rng.uniform(z_upper_limit, z_lower_limit, representative_count).astype(np.float32)
    angles = rng.uniform(0.0, 2.0 * np.pi, representative_count).astype(np.float32)
    size_jitter = rng.uniform(0.90, 1.10, representative_count).astype(np.float32)[:, None]

    cos_a = np.cos(angles)[:, None]
    sin_a = np.sin(angles)[:, None]
    xy_s = base_xy_scale * size_jitter
    z_s = base_z_scale * size_jitter

    vx = (origin_x[:, None] + xy_s * (local_forward[None, :] * cos_a - local_side[None, :] * sin_a)).ravel()
    vy = (origin_y[:, None] + xy_s * (local_forward[None, :] * sin_a + local_side[None, :] * cos_a)).ravel()
    # Scene Z-axis is reversed (0 = surface at top, depth = floor at bottom), so +up is -Z
    vz = (origin_z[:, None] - z_s * local_up[None, :]).ravel()

    n_verts = np.uint16(len(vertices))
    index_offsets = (np.arange(representative_count, dtype=np.uint16) * n_verts)[:, None, None]
    batched_triangles = (triangles[None, :, :] + index_offsets).reshape(-1, 3)
    batched_intensity = np.tile(cell_intensity, representative_count)

    return go.Mesh3d(
        x=vx,
        y=vy,
        z=vz,
        i=batched_triangles[:, 0],
        j=batched_triangles[:, 1],
        k=batched_triangles[:, 2],
        intensity=batched_intensity,
        intensitymode="cell",
        colorscale=colorscale,
        cmin=0,
        cmax=max_palette_index,
        showscale=False,
        flatshading=True,
        opacity=1.0,
        lighting=dict(
            ambient=0.68,
            diffuse=0.82,
            specular=0.25,
            roughness=0.45,
            fresnel=0.15,
        ),
        lightposition=dict(x=100, y=100, z=-200),
        name=f"Shrimp [Low Poly] (representative {representative_count:,} of {stocking_count:,})",
        hoverinfo="skip",
    )
