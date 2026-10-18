"""Stocking and Feed Simulation Module for Penaeus vannamei.

Cross-references stocking density and feed regime against 3D DO/thermal gradients,
evaluates carrying capacity, projects economic harvest margins in Philippine Pesos (PHP ₱),
and computes feasibility verdicts with gradient-driven technical justifications.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np

from .diffusion_engine import SimulationConfig, SimulationResult


class FeedType(str, Enum):
    ORDINARY = "Ordinary Commercial Feed"
    FORTIFIED = "Fortified Growth-Booster Feed"


@dataclass
class FeedProfile:
    name: str
    protein_percent: float
    cost_per_kg_php: float
    fcr: float                          # Feed Conversion Ratio (kg feed / kg shrimp gain)
    growth_multiplier: float            # Multiplier against baseline daily growth
    cycle_days: int                     # Grow-out days to target harvest size (~20g)
    bod_oxygen_factor: float            # g O2 demand per g feed unconsumed/waste


FEED_PROFILES: Dict[FeedType, FeedProfile] = {
    FeedType.ORDINARY: FeedProfile(
        name="Ordinary Commercial Feed",
        protein_percent=34.0,
        cost_per_kg_php=55.0,
        fcr=1.65,
        growth_multiplier=1.0,
        cycle_days=105,
        bod_oxygen_factor=0.12,
    ),
    FeedType.FORTIFIED: FeedProfile(
        name="Fortified Growth-Booster Feed",
        protein_percent=42.0,
        cost_per_kg_php=82.0,
        fcr=1.32,
        growth_multiplier=1.22,
        cycle_days=86,
        bod_oxygen_factor=0.18,
    ),
}


class FeasibilityVerdict(str, Enum):
    FEASIBLE = "FEASIBLE"
    FEASIBLE_CONDITIONAL = "FEASIBLE WITH CONDITIONS"
    NOT_FEASIBLE = "NOT FEASIBLE"


@dataclass
class FeasibilityReportData:
    verdict: FeasibilityVerdict
    badge_color: str                     # CSS color for status badge
    primary_reason: str
    detailed_reasons: List[str]
    min_bottom_do: float                 # Minimum bottom DO recorded (mg/L)
    min_bottom_do_hour: int              # Hour of day (0-23) when lowest DO occurs
    hypoxic_hours_count: int             # Hours where bottom DO < 3.5 mg/L
    lethal_hours_count: int              # Hours where bottom DO < 2.0 mg/L
    max_hypoxic_volume_pct: float        # Peak % volume of pond in hypoxia

    # Stocking Density Metrics
    stocking_density_m2: float           # shrimp per square meter of pond floor
    stocking_density_m3: float           # shrimp per cubic meter
    carrying_capacity_status: str

    # Production & Economic Analysis (PHP ₱)
    target_harvest_weight_g: float
    projected_survival_rate_pct: float
    projected_harvest_biomass_kg: float
    total_feed_consumed_kg: float
    total_feed_cost_php: float
    seed_stocking_cost_php: float        # PL juvenile cost (~0.25 - 0.35 PHP per post-larva)
    total_operating_cost_php: float
    gross_revenue_php: float             # Based on farm-gate price (~300 PHP / kg)
    net_margin_php: float
    roi_percentage: float

    # Actionable Recommendation
    recommended_stocking_count: int
    recommended_feed_type: FeedType
    aeration_schedule_recommendation: Optional[str]


class StockingFeedSimulator:
    """Evaluates biological viability, hypoxia risks, and economic outcomes."""

    def __init__(
        self,
        target_harvest_weight_g: float = 20.0,
        farmgate_price_per_kg_php: float = 300.0,
        postlarvae_cost_each_php: float = 0.30,
    ):
        self.target_harvest_weight_g = target_harvest_weight_g
        self.farmgate_price_per_kg_php = farmgate_price_per_kg_php
        self.postlarvae_cost_each_php = postlarvae_cost_each_php

    def evaluate(
        self,
        config: SimulationConfig,
        result: SimulationResult,
        feed_type: FeedType,
    ) -> FeasibilityReportData:
        """Cross-references simulation gradients with biological thresholds."""
        profile = FEED_PROFILES[feed_type]
        bottom_area_m2 = config.length * config.width
        pond_volume_m3 = bottom_area_m2 * config.depth
        stocking_density_m2 = config.stocking_count / bottom_area_m2
        stocking_density_m3 = config.stocking_count / pond_volume_m3

        # Gradient analysis from simulation result
        # Extract 24-hr cycle minimum bottom DO and hypoxia hours
        min_bottom_do_series = result.min_bottom_do[1:]  # Exclude hour 0 initial condition
        min_bottom_do = float(np.min(min_bottom_do_series))
        min_hour = int(np.argmin(min_bottom_do_series)) + 1
        if min_hour >= 24:
            min_hour = 23

        hypoxic_hours = int(np.sum(min_bottom_do_series < 3.5))
        lethal_hours = int(np.sum(min_bottom_do_series < 2.0))
        max_hypoxic_vol = float(np.max(result.hypoxic_volumes))

        # Biological Survival Rate Modeling
        # Baseline optimal survival in semi-intensive vannamei is 82-88%
        baseline_survival = 0.85
        survival_penalty = 0.0

        if lethal_hours > 0:
            # Drastic mortality if lethal threshold (< 2.0 mg/L) is breached
            survival_penalty += min(0.35 * lethal_hours, 0.70)
        if hypoxic_hours > 0:
            # Chronic stress penalty
            survival_penalty += min(0.04 * hypoxic_hours, 0.25)

        survival_rate = max(0.10, baseline_survival - survival_penalty)

        # Economic Yield and Feed Calculations
        harvested_shrimp = config.stocking_count * survival_rate
        projected_biomass_kg = (harvested_shrimp * self.target_harvest_weight_g) / 1000.0

        # Feed consumed = biomass gain * FCR
        feed_consumed_kg = projected_biomass_kg * profile.fcr
        feed_cost_php = feed_consumed_kg * profile.cost_per_kg_php
        seed_cost_php = config.stocking_count * self.postlarvae_cost_each_php
        # Electricity / aeration / miscellaneous ~ 15% of direct input costs
        misc_ops_cost_php = (feed_cost_php + seed_cost_php) * 0.15
        total_cost_php = feed_cost_php + seed_cost_php + misc_ops_cost_php

        gross_revenue_php = projected_biomass_kg * self.farmgate_price_per_kg_php
        net_margin_php = gross_revenue_php - total_cost_php
        roi_pct = (net_margin_php / max(total_cost_php, 1.0)) * 100.0

        # Feasibility Verdict Decision Matrix
        detailed_reasons: List[str] = []
        aeration_rec: Optional[str] = None

        if lethal_hours > 0 or min_bottom_do < 2.0:
            verdict = FeasibilityVerdict.NOT_FEASIBLE
            badge_color = "#E53E3E"  # Red
            primary_reason = (
                f"Critical Lethal Hypoxia: Bottom DO drops to {min_bottom_do:.2f} mg/L at hour {min_hour:02d}:00, "
                f"causing imminent mass mortality of benthic Penaeus vannamei."
            )
            detailed_reasons.append(
                f"Minimum benthic DO reached {min_bottom_do:.2f} mg/L (threshold lethal limit: 2.00 mg/L)."
            )
            detailed_reasons.append(
                f"Biological oxygen demand from {config.stocking_count:,} shrimp combined with feed decomposition "
                f"exceeds natural surface atmospheric re-aeration capacity."
            )
            detailed_reasons.append(
                f"Stocking density of {stocking_density_m2:.1f} shrimp/m² exceeds natural carrying capacity under current aeration."
            )
            aeration_rec = "Mandatory high-intensity paddlewheel aeration required (2-3 HP/ha), or reduce stocking count."
            carrying_status = "Exceeded (Dangerous Biomass Overload)"

        elif min_bottom_do < 3.5 or hypoxic_hours > 0:
            verdict = FeasibilityVerdict.FEASIBLE_CONDITIONAL
            badge_color = "#DD6B20"  # Amber
            # Find time range of sub-optimal DO
            low_do_hours = [h + 1 for h, v in enumerate(min_bottom_do_series) if v < 3.5]
            start_h = min(low_do_hours) if low_do_hours else 2
            end_h = max(low_do_hours) if low_do_hours else 6

            primary_reason = (
                f"Sub-lethal Respiratory Stress: Bottom DO drops to {min_bottom_do:.2f} mg/L at {min_hour:02d}:00. "
                f"Feasible ONLY if supplemental mechanical aeration is scheduled."
            )
            detailed_reasons.append(
                f"Pre-dawn benthic DO declines between {start_h:02d}:00 and {end_h:02d}:00 due to nocturnal algal respiration and shrimp respiration."
            )
            detailed_reasons.append(
                f"Prolonged exposure to DO below 3.5 mg/L will suppress shrimp appetite, elevate FCR to {profile.fcr * 1.15:.2f}, "
                f"and increase vulnerability to vibriosis infection."
            )
            detailed_reasons.append(
                f"With targeted aeration, projected survival can recover toward the baseline of {baseline_survival * 100:.0f}%."
            )
            aeration_rec = f"Schedule paddlewheel aerators daily from {max(0, start_h - 1):02d}:00 to {min(23, end_h + 1):02d}:00 to maintain DO >= 4.0 mg/L."
            carrying_status = "Near Threshold (Requires Night-time Aeration)"

        else:
            verdict = FeasibilityVerdict.FEASIBLE
            badge_color = "#38A169"  # Green
            primary_reason = (
                f"Excellent Water Quality: Minimum benthic DO remains healthy at {min_bottom_do:.2f} mg/L. "
                f"Pond environment comfortably supports {config.stocking_count:,} Penaeus vannamei."
            )
            detailed_reasons.append(
                f"Bottom DO stays consistently above safe threshold (> 3.50 mg/L) across the entire 24-hour diurnal cycle."
            )
            detailed_reasons.append(
                f"Photosynthetic oxygen generation and re-aeration adequately counterbalance sediment BOD and shrimp respiration."
            )
            detailed_reasons.append(
                f"Projected survival is optimal at {survival_rate * 100:.1f}% under the current biological conditions."
            )
            aeration_rec = "Standard backup aeration; continuous daytime monitoring recommended."
            carrying_status = "Optimal (Well within Pond Carrying Capacity)"

        # Calculate optimal stocking count recommendation (heuristic search)
        if verdict == FeasibilityVerdict.NOT_FEASIBLE:
            rec_stocking = int(config.stocking_count * (min_bottom_do / 3.8))
            rec_stocking = max(5000, min(rec_stocking, config.stocking_count - 5000))
        elif verdict == FeasibilityVerdict.FEASIBLE_CONDITIONAL:
            rec_stocking = config.stocking_count  # Keep count if aeration applied
        else:
            rec_stocking = min(int(config.stocking_count * 1.25), int(bottom_area_m2 * 120))

        return FeasibilityReportData(
            verdict=verdict,
            badge_color=badge_color,
            primary_reason=primary_reason,
            detailed_reasons=detailed_reasons,
            min_bottom_do=min_bottom_do,
            min_bottom_do_hour=min_hour,
            hypoxic_hours_count=hypoxic_hours,
            lethal_hours_count=lethal_hours,
            max_hypoxic_volume_pct=max_hypoxic_vol,
            stocking_density_m2=stocking_density_m2,
            stocking_density_m3=stocking_density_m3,
            carrying_capacity_status=carrying_status,
            target_harvest_weight_g=self.target_harvest_weight_g,
            projected_survival_rate_pct=survival_rate * 100.0,
            projected_harvest_biomass_kg=projected_biomass_kg,
            total_feed_consumed_kg=feed_consumed_kg,
            total_feed_cost_php=feed_cost_php,
            seed_stocking_cost_php=seed_cost_php,
            total_operating_cost_php=total_cost_php,
            gross_revenue_php=gross_revenue_php,
            net_margin_php=net_margin_php,
            roi_percentage=roi_pct,
            recommended_stocking_count=rec_stocking,
            recommended_feed_type=FeedType.FORTIFIED if roi_pct > 25.0 and verdict != FeasibilityVerdict.NOT_FEASIBLE else FeedType.ORDINARY,
            aeration_schedule_recommendation=aeration_rec,
        )
