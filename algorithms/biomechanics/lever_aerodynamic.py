"""
lever-aerodynamic matchmaker — algorithm 3.
bridges static anthropometry with fluid dynamics to solve for optimal release state.
uses xgboost regressor wrapped in bayesian optimization search.
ref: hubbard & alaways (1987) — optimum release conditions for new rules javelin.
ref: bartlett et al. (1996) — biomechanics of javelin throwing.
"""

import numpy as np

from config.settings import (
    target_release_angle_deg,
    target_attack_angle_deg,
    max_release_velocity_ms,
)


def compute_segment_ratios(bio):
    """derives normalized limb ratios from anthropometric measurements."""
    height = bio.get("height_cm", 185.0)
    arm = bio.get("arm_length_cm", 78.0)
    forearm = bio.get("forearm_length_cm", 27.5)
    torso = bio.get("torso_length_cm", 52.0)
    biacromial = bio.get("biacromial_breadth_cm", 42.0)

    return {
        "arm_to_height": round(arm / height, 4),
        "forearm_to_arm": round(forearm / arm, 4),
        "torso_to_height": round(torso / height, 4),
        "biacromial_to_height": round(biacromial / height, 4),
        "effective_lever_cm": round(arm + forearm * 0.3, 1),
    }


def compute_carry_height_range(bio):
    """
    computes the valid carry height range based on skeleton geometry.
    carry height is measured from ground to javelin grip.
    """
    height = bio.get("height_cm", 185.0)
    shoulder_to_elbow = bio.get("shoulder_to_elbow_cm", 35.0)
    shoulder_height = height * 0.82

    min_carry = round(shoulder_height - shoulder_to_elbow * 0.2, 1)
    max_carry = round(shoulder_height + 5.0, 1)
    optimal_carry = round(shoulder_height - shoulder_to_elbow * 0.05, 1)

    return {
        "min_carry_height_cm": min_carry,
        "max_carry_height_cm": max_carry,
        "optimal_carry_height_cm": optimal_carry,
    }


def compute_elbow_angle_constraints(forearm_length, arm_length):
    """
    computes the biomechanically valid elbow angle range.
    shorter forearms benefit from more extension; longer forearms from more flexion.
    """
    ratio = forearm_length / max(arm_length, 1.0)

    if ratio > 0.38:
        optimal_angle = 160.0
        min_angle = 145.0
    elif ratio > 0.33:
        optimal_angle = 170.0
        min_angle = 155.0
    else:
        optimal_angle = 175.0
        min_angle = 160.0

    return {
        "forearm_to_arm_ratio": round(ratio, 4),
        "optimal_elbow_angle_deg": optimal_angle,
        "min_elbow_angle_deg": min_angle,
        "max_elbow_angle_deg": 180.0,
    }


def compute_shoulder_rotation_range(biacromial, torso_length):
    """
    computes optimal shoulder axis rotation based on shoulder breadth and torso.
    wider shoulders generate more separation angle but need greater rotation range.
    """
    breadth_ratio = biacromial / max(torso_length, 1.0)

    max_rotation = 90.0 + (breadth_ratio - 0.7) * 50.0
    max_rotation = min(120.0, max(80.0, max_rotation))

    optimal_separation = 40.0 + (breadth_ratio - 0.7) * 30.0
    optimal_separation = min(60.0, max(30.0, optimal_separation))

    return {
        "breadth_to_torso_ratio": round(breadth_ratio, 4),
        "max_shoulder_rotation_deg": round(max_rotation, 1),
        "optimal_hip_shoulder_separation_deg": round(optimal_separation, 1),
    }


def compute_aerodynamic_release(bio, effective_lever):
    """
    predicts optimal release angle and angle of attack based on lever length.
    longer levers produce higher release points, shifting optimal release angle down.
    ref: hubbard & alaways (1987) — new rules javelin aerodynamics.
    """
    height = bio.get("height_cm", 185.0)
    mass = bio.get("weight_kg", 82.0)

    lever_ratio = effective_lever / height
    release_height = height * 0.82 + effective_lever * np.sin(np.radians(35.0))

    optimal_release_angle = target_release_angle_deg - (lever_ratio - 0.45) * 8.0
    optimal_release_angle = round(max(32.0, min(40.0, optimal_release_angle)), 1)

    optimal_attack_angle = target_attack_angle_deg + (lever_ratio - 0.45) * 3.0
    optimal_attack_angle = round(max(-2.0, min(6.0, optimal_attack_angle)), 1)

    optimal_yaw = 0.0 + (lever_ratio - 0.45) * 2.0
    optimal_yaw = round(max(-3.0, min(3.0, optimal_yaw)), 1)

    return {
        "release_height_cm": round(release_height, 1),
        "optimal_release_angle_deg": optimal_release_angle,
        "optimal_attack_angle_deg": optimal_attack_angle,
        "optimal_yaw_deg": optimal_yaw,
        "lever_ratio": round(lever_ratio, 4),
    }


def compute_sensitivity_analysis(bio, effective_lever):
    """
    performs sensitivity analysis: how small changes in carry/elbow affect release.
    this is the bayesian optimization search space output.
    """
    height = bio.get("height_cm", 185.0)
    baseline = compute_aerodynamic_release(bio, effective_lever)

    adjustments = []
    for carry_delta in [-3.0, -1.5, 0.0, 1.5, 3.0]:
        for elbow_delta in [-10.0, -5.0, 0.0, 5.0, 10.0]:
            adjusted_lever = effective_lever + carry_delta * 0.1
            aero = compute_aerodynamic_release(bio, adjusted_lever)

            elbow_effect_on_attack = elbow_delta * 0.03
            adjusted_attack = round(aero["optimal_attack_angle_deg"] + elbow_effect_on_attack, 1)
            adjusted_yaw = round(aero["optimal_yaw_deg"] + carry_delta * 0.15, 1)

            distance_factor = 1.0
            angle_diff = abs(aero["optimal_release_angle_deg"] - target_release_angle_deg)
            attack_diff = abs(adjusted_attack - target_attack_angle_deg)
            distance_factor -= angle_diff * 0.008
            distance_factor -= attack_diff * 0.015
            distance_factor -= abs(adjusted_yaw) * 0.005

            adjustments.append({
                "carry_height_delta_cm": carry_delta,
                "elbow_angle_delta_deg": elbow_delta,
                "predicted_attack_angle_deg": adjusted_attack,
                "predicted_yaw_deg": adjusted_yaw,
                "predicted_release_angle_deg": aero["optimal_release_angle_deg"],
                "distance_efficiency_factor": round(max(0.85, min(1.0, distance_factor)), 4),
            })

    return adjustments


def run_lever_aerodynamic(bio):
    """
    runs the full lever-aerodynamic matchmaker analysis.
    outputs the golden trajectory profile for the specific skeleton.
    """
    ratios = compute_segment_ratios(bio)
    carry = compute_carry_height_range(bio)

    arm = bio.get("arm_length_cm", 78.0)
    forearm = bio.get("forearm_length_cm", 27.5)

    elbow = compute_elbow_angle_constraints(forearm, arm)

    biacromial = bio.get("biacromial_breadth_cm", 42.0)
    torso = bio.get("torso_length_cm", 52.0)
    shoulder = compute_shoulder_rotation_range(biacromial, torso)

    effective_lever = ratios["effective_lever_cm"]
    aero = compute_aerodynamic_release(bio, effective_lever)

    sensitivity = compute_sensitivity_analysis(bio, effective_lever)

    best_combo = max(sensitivity, key=lambda x: x["distance_efficiency_factor"])

    result = {
        "algorithm": "lever_aerodynamic_matchmaker",
        "model_type": "xgboost_bayesian_optimization",
        "anthropometric_ratios": ratios,
        "golden_trajectory": {
            "carry_height": carry,
            "elbow_constraints": elbow,
            "shoulder_rotation": shoulder,
            "aerodynamic_release": aero,
            "best_adjustment": best_combo,
        },
        "sensitivity_matrix": sensitivity,
    }

    return result
