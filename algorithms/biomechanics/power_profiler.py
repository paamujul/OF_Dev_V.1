"""
muscle-architecture power profiler — algorithm 4.
targets explosive capacity during the final thrust using muscle geometry.
multi-output regression predicting rfd ceiling and crossover stride capacity.
ref: blazevich et al. (2006) — fascicle length-force relationship.
ref: kumagai et al. (2000) — sprint performance and muscle architecture.
"""

import numpy as np

from config.settings import (
    target_runup_velocity_ms,
)


def compute_theoretical_rfd(fascicle_length, pennation_angle, thickness, type_ii_pct):
    """
    computes theoretical rate of force development ceiling from muscle geometry.
    rfd is proportional to type ii content and inversely related to fascicle length.
    ref: blazevich et al. (2006) — fascicle behavior during maximal contractions.
    """
    pcsa = (thickness * 1.0) / np.cos(np.radians(pennation_angle))

    type_ii_factor = type_ii_pct / 100.0
    length_factor = 1.0 / (fascicle_length / 10.0)

    rfd = pcsa * type_ii_factor * length_factor * 1000.0
    return round(rfd, 1)


def compute_crossover_capacity(vl_fascicle, vl_pennation, vl_thickness, vl_type_ii,
                                gm_fascicle, gm_pennation, gm_thickness, gm_type_ii):
    """
    predicts whether the athlete can execute wide aggressive crossover strides.
    combines quadriceps and gastrocnemius architecture for push-off capacity.
    """
    vl_rfd = compute_theoretical_rfd(vl_fascicle, vl_pennation, vl_thickness, vl_type_ii)
    gm_rfd = compute_theoretical_rfd(gm_fascicle, gm_pennation, gm_thickness, gm_type_ii)

    combined_rfd = vl_rfd * 0.65 + gm_rfd * 0.35

    rfd_threshold_for_target = 250.0

    capacity_ratio = combined_rfd / rfd_threshold_for_target

    max_crossover_velocity = target_runup_velocity_ms * min(1.0, capacity_ratio)

    can_execute = capacity_ratio >= 1.0

    return {
        "vl_rfd_ceiling": vl_rfd,
        "gm_rfd_ceiling": gm_rfd,
        "combined_rfd": round(combined_rfd, 1),
        "rfd_threshold": rfd_threshold_for_target,
        "capacity_ratio": round(capacity_ratio, 4),
        "max_crossover_velocity_ms": round(max_crossover_velocity, 2),
        "can_execute_aggressive_crossover": can_execute,
    }


def compute_velocity_maintenance(fascicle_length, type_ii_pct, pennation_angle):
    """
    predicts velocity maintenance through the crossover phase.
    longer fascicles with moderate pennation maintain velocity better.
    ref: kumagai et al. (2000) — fascicle length correlates with sprint velocity.
    """
    length_score = min(1.0, fascicle_length / 12.0)
    fiber_score = min(1.0, type_ii_pct / 70.0)
    pennation_score = 1.0 - max(0, (pennation_angle - 15.0)) / 30.0
    pennation_score = max(0.0, pennation_score)

    maintenance = length_score * 0.40 + fiber_score * 0.35 + pennation_score * 0.25
    return round(min(1.0, max(0.0, maintenance)), 4)


def compute_block_power_readiness(muscle_arch):
    """
    assesses if muscle architecture supports effective block deceleration.
    high pennation angles with large csa excel at force absorption.
    """
    vl = muscle_arch.get("vastus_lateralis", {})
    pennation = vl.get("pennation_angle_deg", 18.0)
    csa = vl.get("muscle_csa_cm2", 80.0)
    thickness = vl.get("muscle_thickness_cm", 3.0)

    force_capacity = (csa / 80.0) * (pennation / 18.0) * (thickness / 3.0)
    readiness = min(1.0, force_capacity)

    return round(readiness, 4)


def run_power_profiler(muscle_arch):
    """
    runs the full multi-output muscle architecture power profile analysis.
    outputs rfd ceilings, crossover capacity, and velocity maintenance.
    """
    vl = muscle_arch.get("vastus_lateralis", {})
    gm = muscle_arch.get("gastrocnemius_medial", {})

    vl_rfd = compute_theoretical_rfd(
        vl.get("fascicle_length_cm", 9.0),
        vl.get("pennation_angle_deg", 18.0),
        vl.get("muscle_thickness_cm", 3.0),
        vl.get("type_ii_pct_csa", 50.0),
    )

    gm_rfd = compute_theoretical_rfd(
        gm.get("fascicle_length_cm", 5.5),
        gm.get("pennation_angle_deg", 22.0),
        gm.get("muscle_thickness_cm", 2.0),
        gm.get("type_ii_pct_csa", 50.0),
    )

    crossover = compute_crossover_capacity(
        vl.get("fascicle_length_cm", 9.0),
        vl.get("pennation_angle_deg", 18.0),
        vl.get("muscle_thickness_cm", 3.0),
        vl.get("type_ii_pct_csa", 50.0),
        gm.get("fascicle_length_cm", 5.5),
        gm.get("pennation_angle_deg", 22.0),
        gm.get("muscle_thickness_cm", 2.0),
        gm.get("type_ii_pct_csa", 50.0),
    )

    vel_maintenance = compute_velocity_maintenance(
        vl.get("fascicle_length_cm", 9.0),
        vl.get("type_ii_pct_csa", 50.0),
        vl.get("pennation_angle_deg", 18.0),
    )

    block_readiness = compute_block_power_readiness(muscle_arch)

    limiting_factors = []
    if vl.get("fascicle_length_cm", 9.0) < 8.5:
        limiting_factors.append("short_vl_fascicles_limit_contraction_velocity")
    if vl.get("type_ii_pct_csa", 50.0) < 55.0:
        limiting_factors.append("low_type_ii_proportion_limits_rfd")
    if vl.get("pennation_angle_deg", 18.0) > 25.0:
        limiting_factors.append("high_pennation_limits_shortening_velocity")
    if gm.get("muscle_thickness_cm", 2.0) < 1.8:
        limiting_factors.append("thin_gastrocnemius_limits_pushoff")

    result = {
        "algorithm": "muscle_architecture_power_profiler",
        "model_type": "multi_output_regression",
        "rfd_analysis": {
            "vastus_lateralis_rfd_ceiling": vl_rfd,
            "gastrocnemius_rfd_ceiling": gm_rfd,
        },
        "crossover_analysis": crossover,
        "velocity_maintenance_index": vel_maintenance,
        "block_power_readiness": block_readiness,
        "limiting_factors": limiting_factors,
        "muscle_inputs": {
            "vastus_lateralis": vl,
            "gastrocnemius_medial": gm,
        },
    }

    return result
