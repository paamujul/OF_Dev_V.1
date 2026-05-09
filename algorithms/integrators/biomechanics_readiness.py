"""
biomechanics readiness integrator.
aggregates all 5 biomechanical algorithms into a composite output.
ref: project plan — biomechanics layer integrating biological markers with technique.
"""

import json
import os
from datetime import datetime

from algorithms.biomechanics.temporal_sequencing import run_temporal_sequencing
from algorithms.biomechanics.block_mechanics_pinn import run_block_mechanics
from algorithms.biomechanics.lever_aerodynamic import run_lever_aerodynamic
from algorithms.biomechanics.power_profiler import run_power_profiler
from algorithms.biomechanics.technique_degradation import run_technique_degradation


def compute_biomechanics_composite(temporal, block, lever, power, degradation):
    """
    computes a composite biomechanics readiness score from all 5 algorithms.
    weights reflect the contribution of each subsystem to throw performance.
    """
    temporal_score = 1.0 - temporal["summary"]["avg_energy_leakage"]

    block_score = block["summary"]["block_effectiveness_at_target"]

    best_eff = lever["golden_trajectory"]["best_adjustment"]["distance_efficiency_factor"]
    lever_score = best_eff

    power_score = min(1.0, power["crossover_analysis"]["capacity_ratio"])

    degradation_risk = degradation["summary"]["technical_degradation_risk_score"] / 100.0
    degradation_score = 1.0 - degradation_risk

    weights = {
        "temporal_sequencing": 0.20,
        "block_mechanics": 0.25,
        "lever_aerodynamic": 0.20,
        "power_profiler": 0.20,
        "technique_degradation": 0.15,
    }

    composite = (
        temporal_score * weights["temporal_sequencing"]
        + block_score * weights["block_mechanics"]
        + lever_score * weights["lever_aerodynamic"]
        + power_score * weights["power_profiler"]
        + degradation_score * weights["technique_degradation"]
    )

    composite = round(composite * 100.0, 2)

    if composite >= 85:
        protocol = "full_technical_loading"
    elif composite >= 70:
        protocol = "moderate_technical_focus"
    elif composite >= 55:
        protocol = "corrective_drill_emphasis"
    else:
        protocol = "structural_rehabilitation"

    component_scores = {
        "temporal_sequencing": round(temporal_score * 100, 2),
        "block_mechanics": round(block_score * 100, 2),
        "lever_aerodynamic": round(lever_score * 100, 2),
        "power_profiler": round(power_score * 100, 2),
        "technique_degradation": round(degradation_score * 100, 2),
    }

    return composite, protocol, component_scores, weights


def compute_biomechanics_readiness(athlete):
    """
    runs all 5 biomechanical algorithms and produces composite readiness.
    """
    temporal_result = run_temporal_sequencing(athlete.emg, athlete.muscle_arch)
    block_result = run_block_mechanics(athlete.bio, athlete.muscle_arch)
    lever_result = run_lever_aerodynamic(athlete.bio)
    power_result = run_power_profiler(athlete.muscle_arch)
    degradation_result = run_technique_degradation(
        athlete.bio, athlete.emg, athlete.travel
    )

    composite, protocol, component_scores, weights = compute_biomechanics_composite(
        temporal_result, block_result, lever_result, power_result, degradation_result
    )

    flags = []

    if temporal_result["summary"]["avg_energy_leakage"] > 0.25:
        flags.append({
            "source": "temporal_sequencing",
            "issue": "high_energy_leakage",
            "detail": "proximal-to-distal firing sequence has excessive energy loss",
        })

    if not block_result["summary"]["target_is_safe"]:
        flags.append({
            "source": "block_mechanics",
            "issue": "target_velocity_unsafe",
            "detail": f"structural capacity insufficient for {block_result['summary']['target_runway_velocity_ms']} m/s",
        })

    if not power_result["crossover_analysis"]["can_execute_aggressive_crossover"]:
        flags.append({
            "source": "power_profiler",
            "issue": "crossover_capacity_limited",
            "detail": "muscle architecture cannot support aggressive crossover stride",
        })

    if degradation_result["summary"]["risk_level"] in ["high"]:
        flags.append({
            "source": "technique_degradation",
            "issue": "high_environmental_risk",
            "detail": degradation_result["summary"]["failure_description"],
        })

    result = {
        "algorithm": "biomechanics_readiness",
        "biomechanics_composite_score": composite,
        "protocol_recommendation": protocol,
        "component_scores": component_scores,
        "weights": weights,
        "flags": flags,
        "flag_count": len(flags),
        "components": {
            "temporal_sequencing": temporal_result,
            "block_mechanics": block_result,
            "lever_aerodynamic": lever_result,
            "power_profiler": power_result,
            "technique_degradation": degradation_result,
        },
    }

    return result
