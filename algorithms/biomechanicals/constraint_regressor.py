"""
dynamic biomechanical constraint regressor (mobility & stiffness).
predicts daily rom loss and outputs modified kinematic constraint profile.
ref: stecco et al. (2013), journal of anatomy — hyaluronan viscosity and fascia.
ref: dattilo et al. (2011), medical hypotheses — sws and gh for ecm repair.
ref: abate et al. (2013), frontiers in endocrinology — ages and collagen crosslinking.
ref: teng et al. (2021), journal of cellular physiology — zinc and mmp activity.
ref: waterhouse et al. (2005), chronobiology international — temperature and rom.
"""

import statistics

from config.settings import (
    constraint_deep_sleep_optimal_percent,
    constraint_deep_sleep_critical_percent,
    constraint_glucose_optimal_mg_dl,
    constraint_glucose_age_threshold_mg_dl,
    constraint_zinc_optimal_ug_dl,
    constraint_zinc_critical_ug_dl,
    constraint_b12_optimal_pg_ml,
    constraint_b12_critical_pg_ml,
    constraint_baseline_rom_deg,
    constraint_max_rom_loss_deg,
    constraint_temp_weight,
    constraint_sleep_weight,
    constraint_glucose_weight,
    constraint_zinc_weight,
    constraint_b12_weight,
)


def compute_thermal_stiffness(skin_temp_history):
    """
    elevated nocturnal skin temp correlates with inflammatory cytokines.
    inflammation changes hyaluronic acid viscosity from lubricant to glue.
    ref: stecco et al. (2013), journal of anatomy.
    """
    avg_temp = statistics.mean(skin_temp_history)
    temp_baseline = 33.3

    if avg_temp > temp_baseline + 1.0:
        penalty = min(1.0, (avg_temp - temp_baseline) / 2.0)
    elif avg_temp < temp_baseline - 1.0:
        penalty = min(1.0, (temp_baseline - avg_temp) / 3.0)
    else:
        penalty = 0.0

    return penalty, {"avg_skin_temp": round(avg_temp, 2), "baseline": temp_baseline}


def compute_deep_sleep_stiffness(deep_sleep_percent):
    """
    sws is the exclusive window for peak gh secretion.
    gh is required for collagen synthesis and ecm remodeling.
    ref: dattilo et al. (2011), medical hypotheses.
    """
    if deep_sleep_percent >= constraint_deep_sleep_optimal_percent:
        penalty = 0.0
    elif deep_sleep_percent >= constraint_deep_sleep_critical_percent:
        ds_range = constraint_deep_sleep_optimal_percent - constraint_deep_sleep_critical_percent
        ds_deficit = constraint_deep_sleep_optimal_percent - deep_sleep_percent
        penalty = ds_deficit / ds_range
    else:
        penalty = 1.0

    return penalty, {"deep_sleep_percent": round(deep_sleep_percent, 1)}


def compute_glucose_stiffness(fasting_glucose):
    """
    elevated glucose drives age formation and collagen crosslinking.
    ref: abate et al. (2013), frontiers in endocrinology.
    """
    if fasting_glucose <= constraint_glucose_optimal_mg_dl:
        penalty = 0.0
    elif fasting_glucose <= constraint_glucose_age_threshold_mg_dl:
        glucose_range = constraint_glucose_age_threshold_mg_dl - constraint_glucose_optimal_mg_dl
        glucose_excess = fasting_glucose - constraint_glucose_optimal_mg_dl
        penalty = glucose_excess / glucose_range
    else:
        penalty = 1.0

    return penalty, {"fasting_glucose_mg_dl": fasting_glucose}


def compute_zinc_stiffness(zinc_level):
    """
    zinc is a cofactor for matrix metalloproteinases (mmps).
    low zinc arrests fascial remodeling and locks tissue in fibrotic state.
    ref: teng et al. (2021), journal of cellular physiology.
    """
    if zinc_level >= constraint_zinc_optimal_ug_dl:
        penalty = 0.0
    elif zinc_level >= constraint_zinc_critical_ug_dl:
        zn_range = constraint_zinc_optimal_ug_dl - constraint_zinc_critical_ug_dl
        zn_deficit = constraint_zinc_optimal_ug_dl - zinc_level
        penalty = zn_deficit / zn_range
    else:
        penalty = 1.0

    return penalty, {"zinc_ug_dl": zinc_level}


def compute_b12_stiffness(b12_level):
    """
    b12 deficiency alters mechanoreceptor signaling and increases muscle guarding.
    ref: waterhouse et al. (2005), chronobiology international.
    """
    if b12_level >= constraint_b12_optimal_pg_ml:
        penalty = 0.0
    elif b12_level >= constraint_b12_critical_pg_ml:
        b12_range = constraint_b12_optimal_pg_ml - constraint_b12_critical_pg_ml
        b12_deficit = constraint_b12_optimal_pg_ml - b12_level
        penalty = b12_deficit / b12_range
    else:
        penalty = 1.0

    return penalty, {"vitamin_b12_pg_ml": b12_level}


def compute_kinematic_constraints(athlete):
    """
    master constraint regressor.
    predicts daily rom loss and outputs the achievable shoulder er for the session.
    """
    skin_temps = athlete.wearables.get(
        "skin_temp_celsius_7d",
        [33.3] * 7,
    )
    temp_penalty, temp_details = compute_thermal_stiffness(skin_temps)

    deep_sleep = athlete.avg_deep_sleep_percent()
    sleep_penalty, sleep_details = compute_deep_sleep_stiffness(deep_sleep)

    metabolic = athlete.bloodwork.get("metabolic_panel", {})
    glucose = metabolic.get("fasting_glucose_mg_dl", constraint_glucose_optimal_mg_dl)
    glucose_penalty, glucose_details = compute_glucose_stiffness(glucose)

    nutritional = athlete.bloodwork.get("nutritional_panel", {})
    zinc = nutritional.get("zinc_ug_dl", constraint_zinc_optimal_ug_dl)
    zinc_penalty, zinc_details = compute_zinc_stiffness(zinc)

    b12 = nutritional.get("vitamin_b12_pg_ml", constraint_b12_optimal_pg_ml)
    b12_penalty, b12_details = compute_b12_stiffness(b12)

    composite_penalty = (
        constraint_temp_weight * temp_penalty
        + constraint_sleep_weight * sleep_penalty
        + constraint_glucose_weight * glucose_penalty
        + constraint_zinc_weight * zinc_penalty
        + constraint_b12_weight * b12_penalty
    )

    stiffness_increase_percent = composite_penalty * 100.0
    delta_rom = composite_penalty * constraint_max_rom_loss_deg
    achievable_rom = constraint_baseline_rom_deg - delta_rom

    if delta_rom > 12:
        severity = "severe_restriction"
        recommendation = (
            f"achievable shoulder er today: {round(achievable_rom, 1)} deg — "
            "adjust trunk lean to compensate for restricted mobility"
        )
    elif delta_rom > 6:
        severity = "moderate_restriction"
        recommendation = (
            f"reduced rom by {round(delta_rom, 1)} deg — "
            "modify release yaw and elbow angle for optimal energy transfer"
        )
    elif delta_rom > 2:
        severity = "mild_restriction"
        recommendation = "minor stiffness detected — extended warmup recommended"
    else:
        severity = "optimal"
        recommendation = "full range of motion available"

    result = {
        "algorithm": "constraint_regressor",
        "stiffness_increase_percent": round(stiffness_increase_percent, 2),
        "delta_rom_deg": round(delta_rom, 2),
        "achievable_rom_deg": round(achievable_rom, 2),
        "baseline_rom_deg": constraint_baseline_rom_deg,
        "severity": severity,
        "recommendation": recommendation,
        "component_penalties": {
            "thermal": round(temp_penalty, 3),
            "deep_sleep": round(sleep_penalty, 3),
            "glucose": round(glucose_penalty, 3),
            "zinc": round(zinc_penalty, 3),
            "b12": round(b12_penalty, 3),
        },
        "thermal_details": temp_details,
        "sleep_details": sleep_details,
        "glucose_details": glucose_details,
        "zinc_details": zinc_details,
        "b12_details": b12_details,
    }
    return result
