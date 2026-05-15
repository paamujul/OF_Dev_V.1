"""
autonomic & neural sequencing predictor (ansp).
predicts proximal-to-distal transfer timing degradation in milliseconds.
ref: frontiers in sports and active living (2025) — hrv and cns fatigue.
ref: journal of sports medicine (2012) — sleep deprivation and reaction time.
ref: walker et al. — rem sleep and motor sequence consolidation.
ref: nutrients — magnesium and neuromuscular transmission.
"""

import math
import statistics

from config.settings import (
    ansp_hrv_weight,
    ansp_sleep_weight,
    ansp_cortisol_weight,
    ansp_magnesium_weight,
    ansp_rem_optimal_percent,
    ansp_rem_critical_percent,
    ansp_magnesium_optimal_mg_dl,
    ansp_magnesium_critical_mg_dl,
    ansp_baseline_lag_ms,
    ansp_max_lag_ms,
    ansp_lag_hrv_coefficient,
    ansp_lag_sleep_coefficient,
    ansp_lag_cortisol_coefficient,
    ansp_lag_magnesium_coefficient,
    ftc_deficit_threshold,
)


def compute_hrv_neural_penalty(hrv_history):
    """
    hrv z-score penalty for cns fatigue.
    depressed rmssd indicates sympathetic dominance and degraded motor timing.
    ref: frontiers in sports and active living (2025).
    """
    ln_values = [math.log(v) for v in hrv_history]
    mean_ln = statistics.mean(ln_values)
    std_ln = statistics.stdev(ln_values)

    if std_ln == 0:
        return 0.0, {"z_hrv": 0.0}

    current_ln = ln_values[-1]
    z_hrv = (current_ln - mean_ln) / std_ln

    penalty = max(0.0, -z_hrv) * ansp_lag_hrv_coefficient

    return penalty, {"z_hrv": round(z_hrv, 3)}


def compute_sleep_neural_penalty(rem_percent, sleep_debt):
    """
    rem and sleep debt penalty for motor sequence consolidation.
    ref: walker et al. — rem is required for neural reorganization.
    ref: journal of sports medicine (2012) — sleep deprivation impairs reaction time.
    """
    if rem_percent >= ansp_rem_optimal_percent:
        rem_penalty = 0.0
    elif rem_percent >= ansp_rem_critical_percent:
        rem_range = ansp_rem_optimal_percent - ansp_rem_critical_percent
        rem_deficit = ansp_rem_optimal_percent - rem_percent
        rem_penalty = (rem_deficit / rem_range) * ansp_lag_sleep_coefficient
    else:
        rem_penalty = ansp_lag_sleep_coefficient

    debt_penalty = min(sleep_debt, 3.0) * 1.0

    total = rem_penalty + debt_penalty

    details = {
        "rem_percent": round(rem_percent, 1),
        "rem_penalty": round(rem_penalty, 2),
        "debt_penalty": round(debt_penalty, 2),
    }
    return total, details


def compute_cortisol_neural_penalty(ft_ratio, ft_baseline):
    """
    cortisol-driven neural noise penalty.
    high cortisol increases antagonist co-activation and delays sequencing.
    ref: hayes et al. (2015), chronobiology international.
    """
    if ft_baseline <= 0:
        return 0.0, {"ftc_deficit_percent": 0.0}

    deficit = (ft_baseline - ft_ratio) / ft_baseline
    deficit = max(0.0, deficit)

    if deficit > ftc_deficit_threshold:
        penalty = ansp_lag_cortisol_coefficient * (deficit / ftc_deficit_threshold)
    else:
        penalty = ansp_lag_cortisol_coefficient * (deficit / ftc_deficit_threshold) * 0.5

    details = {
        "ftc_deficit_percent": round(deficit * 100, 2),
        "is_catabolic": deficit > ftc_deficit_threshold,
    }
    return penalty, details


def compute_magnesium_penalty(magnesium_level):
    """
    magnesium deficiency penalty for neuromuscular transmission.
    ref: nutrients — mg regulates calcium channels at motor endplate.
    """
    if magnesium_level >= ansp_magnesium_optimal_mg_dl:
        penalty = 0.0
    elif magnesium_level >= ansp_magnesium_critical_mg_dl:
        mg_range = ansp_magnesium_optimal_mg_dl - ansp_magnesium_critical_mg_dl
        mg_deficit = ansp_magnesium_optimal_mg_dl - magnesium_level
        penalty = (mg_deficit / mg_range) * ansp_lag_magnesium_coefficient
    else:
        penalty = ansp_lag_magnesium_coefficient

    return penalty, {"magnesium_mg_dl": magnesium_level}


def compute_proprioceptive_lag(athlete):
    """
    master ansp function.
    predicts timing degradation in milliseconds for proximal-to-distal transfer.
    """
    hrv_history = athlete.wearables["hrv_rmssd_30d"]
    hrv_penalty, hrv_details = compute_hrv_neural_penalty(hrv_history)

    rem_percent = athlete.avg_rem_percent()
    sleep_debt = athlete.sleep_debt()
    sleep_penalty, sleep_details = compute_sleep_neural_penalty(rem_percent, sleep_debt)

    hormonal = athlete.bloodwork.get("hormonal_panel", {})
    ft_ratio = hormonal.get("ft_cortisol_ratio", 1.0)
    ft_baseline = hormonal.get("ft_cortisol_ratio_baseline", 1.0)
    cortisol_penalty, cortisol_details = compute_cortisol_neural_penalty(
        ft_ratio, ft_baseline
    )

    nutritional = athlete.bloodwork.get("nutritional_panel", {})
    magnesium = nutritional.get("magnesium_mg_dl", ansp_magnesium_optimal_mg_dl)
    mg_penalty, mg_details = compute_magnesium_penalty(magnesium)

    weighted_lag = (
        ansp_hrv_weight * hrv_penalty
        + ansp_sleep_weight * sleep_penalty
        + ansp_cortisol_weight * cortisol_penalty
        + ansp_magnesium_weight * mg_penalty
    )

    predicted_lag_ms = ansp_baseline_lag_ms + weighted_lag
    predicted_lag_ms = min(predicted_lag_ms, ansp_max_lag_ms)
    predicted_lag_ms = max(0.0, predicted_lag_ms)

    if predicted_lag_ms > 25:
        severity = "severe"
        recommendation = (
            "initiate arm strike earlier to compensate for "
            f"{round(predicted_lag_ms, 1)}ms neural lag — "
            "reduce maximal throws and focus on submaximal sequencing drills"
        )
    elif predicted_lag_ms > 15:
        severity = "moderate"
        recommendation = (
            "verbal cue adjustment needed — "
            f"compensate for {round(predicted_lag_ms, 1)}ms timing degradation"
        )
    elif predicted_lag_ms > 5:
        severity = "mild"
        recommendation = "minor timing offset detected — monitor during warmup"
    else:
        severity = "optimal"
        recommendation = "neural sequencing within normal parameters"

    result = {
        "algorithm": "neural_sequencing",
        "predicted_lag_ms": round(predicted_lag_ms, 2),
        "severity": severity,
        "recommendation": recommendation,
        "component_penalties": {
            "hrv": round(hrv_penalty, 3),
            "sleep": round(sleep_penalty, 3),
            "cortisol": round(cortisol_penalty, 3),
            "magnesium": round(mg_penalty, 3),
        },
        "hrv_details": hrv_details,
        "sleep_details": sleep_details,
        "cortisol_details": cortisol_details,
        "magnesium_details": mg_details,
    }
    return result
