"""Feasibility Report Generator for EcoPrawn.

Compiles simulation parameters, 3D gradient dynamics, biological feasibility verdicts,
and Matplotlib contour figures into a standalone, printable HTML research report.
"""

import base64
from datetime import datetime
import io
from typing import Optional
import matplotlib.pyplot as plt

from models.diffusion_engine import SimulationConfig, SimulationResult
from models.stocking_feed_simulator import FeasibilityReportData, FeedType
from visualization.contour_plots import PondContourPlotter


class FeasibilityReportGenerator:
    """Generates standalone publication-ready HTML simulation report."""

    @staticmethod
    def _figure_to_base64(fig: plt.Figure) -> str:
        """Encodes Matplotlib figure to base64 PNG string."""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=130)
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)
        return img_str

    @classmethod
    def generate_html_report(
        cls,
        config: SimulationConfig,
        result: SimulationResult,
        report_data: FeasibilityReportData,
        feed_type: FeedType,
        location_label: str = "Caloocan City, Metro Manila",
    ) -> str:
        """Builds complete standalone HTML report."""
        timestamp_now = datetime.now().strftime("%B %d, %Y - %I:%M %p")

        # Render figures to base64
        # 1. Cross-section at minimum bottom DO hour
        fig_cross = PondContourPlotter.plot_vertical_cross_section(
            result, hour_idx=report_data.min_bottom_do_hour, hypoxia_threshold=3.5
        )
        cross_b64 = cls._figure_to_base64(fig_cross)

        # 2. Benthic floor contour
        fig_floor = PondContourPlotter.plot_benthic_floor_contour(
            result, hour_idx=report_data.min_bottom_do_hour, hypoxia_threshold=3.5
        )
        floor_b64 = cls._figure_to_base64(fig_floor)

        # 3. 24-hr time-series
        fig_ts = PondContourPlotter.plot_diurnal_summary_timeseries(result, hypoxia_threshold=3.5)
        ts_b64 = cls._figure_to_base64(fig_ts)

        # Badge color styles
        badge_bg = (
            "#DEF7EC" if report_data.verdict.value == "FEASIBLE"
            else "#FEF08A" if report_data.verdict.value == "FEASIBLE WITH CONDITIONS"
            else "#FDE8E8"
        )
        badge_text = (
            "#03543F" if report_data.verdict.value == "FEASIBLE"
            else "#713F12" if report_data.verdict.value == "FEASIBLE WITH CONDITIONS"
            else "#9B1C1C"
        )

        reasons_html = "".join([f"<li>{r}</li>" for r in report_data.detailed_reasons])
        aeration_html = (
            f"<div class='alert-box'><strong>Aeration Schedule Recommendation:</strong> {report_data.aeration_schedule_recommendation}</div>"
            if report_data.aeration_schedule_recommendation
            else ""
        )

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EcoPrawn Aquaculture Feasibility & Diffusion Report</title>
  <style>
    @page {{ size: A4; margin: 15mm; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1A202C;
      background-color: #F7FAFC;
      margin: 0;
      padding: 24px;
      line-height: 1.5;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
      background: #FFFFFF;
      padding: 36px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }}
    .header {{
      border-bottom: 2px solid #E2E8F0;
      padding-bottom: 18px;
      margin-bottom: 24px;
    }}
    .header h1 {{
      font-size: 22px;
      margin: 0 0 6px 0;
      color: #1A365D;
    }}
    .header p {{
      margin: 0;
      color: #718096;
      font-size: 13px;
    }}
    .verdict-banner {{
      background: {badge_bg};
      border-left: 6px solid {report_data.badge_color};
      color: {badge_text};
      padding: 16px 20px;
      border-radius: 4px;
      margin-bottom: 24px;
    }}
    .verdict-title {{
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 6px;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
      margin-bottom: 24px;
    }}
    .card {{
      background: #F8FAFC;
      border: 1px solid #E2E8F0;
      border-radius: 6px;
      padding: 16px;
    }}
    .card h3 {{
      margin-top: 0;
      margin-bottom: 12px;
      font-size: 14px;
      color: #2D3748;
      border-bottom: 1px solid #E2E8F0;
      padding-bottom: 6px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 6px 8px;
      text-align: left;
      border-bottom: 1px solid #EDF2F7;
    }}
    th {{ color: #4A5568; }}
    td.num {{ text-align: right; font-weight: 500; }}
    .alert-box {{
      background: #EFF6FF;
      border: 1px solid #BFDBFE;
      color: #1E40AF;
      padding: 12px;
      border-radius: 4px;
      margin: 16px 0;
      font-size: 13px;
    }}
    .section-title {{
      font-size: 16px;
      color: #2D3748;
      margin: 28px 0 12px 0;
      border-bottom: 1px solid #E2E8F0;
      padding-bottom: 6px;
    }}
    .figure-container {{
      text-align: center;
      margin: 20px 0;
    }}
    .figure-container img {{
      max-width: 100%;
      border: 1px solid #E2E8F0;
      border-radius: 6px;
    }}
    .figure-caption {{
      font-size: 12px;
      color: #718096;
      margin-top: 6px;
      font-style: italic;
    }}
    ul {{ margin: 6px 0 0 20px; padding: 0; font-size: 13px; }}
    li {{ margin-bottom: 4px; }}
    @media print {{
      body {{ background: white; padding: 0; }}
      .container {{ box-shadow: none; padding: 0; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>EcoPrawn Water Quality Diffusion & Stocking Feasibility</h1>
      <p>Generated: {timestamp_now}</p>
      <p>Target Organism: <em>Penaeus vannamei</em> (Pacific White Shrimp) | Location: {location_label}</p>
    </div>

    <div class="verdict-banner">
      <div class="verdict-title">FEASIBILITY VERDICT: {report_data.verdict.value}</div>
      <div>{report_data.primary_reason}</div>
      {aeration_html}
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>1. Pond & Stocking Specifications</h3>
        <table>
          <tr><th>Pond Geometry</th><td class="num">{config.length:.1f}m × {config.width:.1f}m × {config.depth:.1f}m ({config.length * config.width * config.depth:.0f} m³)</td></tr>
          <tr><th>Discretization Grid</th><td class="num">{config.nx} × {config.ny} × {config.nz} cells</td></tr>
          <tr><th>Stocking Count</th><td class="num">{config.stocking_count:,} juveniles</td></tr>
          <tr><th>Stocking Density</th><td class="num">{report_data.stocking_density_m2:.1f} shrimp/m² ({report_data.stocking_density_m3:.1f}/m³)</td></tr>
          <tr><th>Carrying Status</th><td class="num">{report_data.carrying_capacity_status}</td></tr>
          <tr><th>Feed Regimen</th><td class="num">{feed_type.value}</td></tr>
        </table>
      </div>

      <div class="card">
        <h3>2. Water Quality & Hypoxia Gradients</h3>
        <table>
          <tr><th>Minimum Bottom DO</th><td class="num"><strong>{report_data.min_bottom_do:.2f} mg/L</strong> (at {report_data.min_bottom_do_hour:02d}:00)</td></tr>
          <tr><th>Hypoxic Hours (<3.5 mg/L)</th><td class="num">{report_data.hypoxic_hours_count} hours</td></tr>
          <tr><th>Lethal Hours (<2.0 mg/L)</th><td class="num">{report_data.lethal_hours_count} hours</td></tr>
          <tr><th>Max Hypoxic Volume %</th><td class="num">{report_data.max_hypoxic_volume_pct:.1f}% of pond volume</td></tr>
          <tr><th>Mechanical Aeration</th><td class="num">{'Active' if config.aeration_enabled else 'Disabled'}</td></tr>
        </table>
      </div>
    </div>

    <div class="card" style="margin-bottom: 24px;">
      <h3>3. Technical Reasoning & Gradient Justifications</h3>
      <ul>{reasons_html}</ul>
    </div>

    <div class="card" style="margin-bottom: 24px;">
      <h3>4. Production Outlook</h3>
      <table>
        <tr>
          <th>Projected Harvest Biomass</th><td class="num">{report_data.projected_harvest_biomass_kg:.1f} kg (Survival: {report_data.projected_survival_rate_pct:.1f}%)</td>
          <th>Total Feed Consumed</th><td class="num">{report_data.total_feed_consumed_kg:.1f} kg</td>
        </tr>
        <tr>
          <th>Target Harvest Weight</th><td class="num">{report_data.target_harvest_weight_g:.1f} g per shrimp</td>
          <th>Recommended Stocking</th><td class="num">{report_data.recommended_stocking_count:,} shrimp</td>
        </tr>
      </table>
    </div>

    <div class="section-title">5. Contour Visualizations</div>

    <div class="figure-container">
      <img src="data:image/png;base64,{cross_b64}" alt="Vertical Cross-Section">
      <div class="figure-caption">Figure 1: 2D Vertical Depth Cross-Section (X-Z Plane) showing Thermal and DO Stratification at hour {report_data.min_bottom_do_hour:02d}:00.</div>
    </div>

    <div class="figure-container">
      <img src="data:image/png;base64,{floor_b64}" alt="Benthic Floor Contour">
      <div class="figure-caption">Figure 2: 2D Benthic Floor Habitat Contour (X-Y Plane at Z={config.depth:.1f}m) where Penaeus vannamei dwell.</div>
    </div>

    <div class="figure-container">
      <img src="data:image/png;base64,{ts_b64}" alt="24-Hour Diurnal Dynamics">
      <div class="figure-caption">Figure 3: 24-Hour Diurnal Time Series of Surface DO, Bottom DO, and Hypoxic Pond Volume Fraction.</div>
    </div>

    <div style="margin-top: 36px; padding-top: 12px; border-top: 1px solid #E2E8F0; font-size: 11px; color: #A0AEC0; text-align: center;">
      EcoPrawn Aquaculture Simulation | Generated: {timestamp_now}
    </div>
  </div>
</body>
</html>
"""
        return html_content
