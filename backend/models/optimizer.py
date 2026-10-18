"""Carrying Capacity and Stocking Scenario Optimizer.

Simulates multiple stocking density and feed regime permutations to find
the maximum sustainable stocking capacity and optimal economic yield.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

from .diffusion_engine import Pond3DDiffusionSolver, SimulationConfig
from .stocking_feed_simulator import (
    FEED_PROFILES,
    FeasibilityReportData,
    FeasibilityVerdict,
    FeedType,
    StockingFeedSimulator,
)


@dataclass
class ScenarioComparisonItem:
    stocking_count: int
    feed_type: FeedType
    density_m2: float
    min_bottom_do: float
    verdict: FeasibilityVerdict
    harvest_biomass_kg: float
    feed_cost_php: float
    total_cost_php: float
    net_profit_php: float
    roi_pct: float


class StockingOptimizer:
    """Finds optimal stocking count and feed selection given pond geometry."""

    def __init__(self, base_config: SimulationConfig, solar: np.ndarray, air_temp: np.ndarray):
        self.base_cfg = base_config
        self.solar = solar
        self.air_temp = air_temp
        self.evaluator = StockingFeedSimulator()

    def run_scenario_matrix(
        self,
        stocking_counts: List[int],
        feed_types: List[FeedType] = [FeedType.ORDINARY, FeedType.FORTIFIED],
    ) -> List[ScenarioComparisonItem]:
        """Runs fast multi-scenario sweep across stocking counts and feeds."""
        results: List[ScenarioComparisonItem] = []

        # For fast sweep, use a slightly coarser grid to evaluate multiple scenarios in seconds
        coarse_nx, coarse_ny, coarse_nz = 12, 12, 8
        bottom_area_m2 = self.base_cfg.length * self.base_cfg.width

        for count in stocking_counts:
            for f_type in feed_types:
                profile = FEED_PROFILES[f_type]
                cfg = SimulationConfig(
                    length=self.base_cfg.length,
                    width=self.base_cfg.width,
                    depth=self.base_cfg.depth,
                    nx=coarse_nx,
                    ny=coarse_ny,
                    nz=coarse_nz,
                    stocking_count=count,
                    individual_weight_g=self.base_cfg.individual_weight_g,
                    feed_protein_ratio=profile.protein_percent / 100.0,
                    feed_bod_factor=profile.bod_oxygen_factor,
                    aeration_enabled=self.base_cfg.aeration_enabled,
                    aeration_start_hour=self.base_cfg.aeration_start_hour,
                    aeration_end_hour=self.base_cfg.aeration_end_hour,
                )
                solver = Pond3DDiffusionSolver(cfg)
                sim_res = solver.solve(
                    solar_irradiance=self.solar,
                    air_temperature=self.air_temp,
                    dt_seconds=60.0,  # Fast sub-stepping
                )
                report = self.evaluator.evaluate(cfg, sim_res, f_type)

                results.append(
                    ScenarioComparisonItem(
                        stocking_count=count,
                        feed_type=f_type,
                        density_m2=count / bottom_area_m2,
                        min_bottom_do=report.min_bottom_do,
                        verdict=report.verdict,
                        harvest_biomass_kg=report.projected_harvest_biomass_kg,
                        feed_cost_php=report.total_feed_cost_php,
                        total_cost_php=report.total_operating_cost_php,
                        net_profit_php=report.net_margin_php,
                        roi_pct=report.roi_percentage,
                    )
                )

        return results
