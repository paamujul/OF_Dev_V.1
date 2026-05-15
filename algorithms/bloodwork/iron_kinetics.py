"""
iron panel multi-compartment pharmacokinetic model.
ref: sim et al. (2019), european journal of applied physiology — iron review.
ref: project plan flowchart — first-order exponential accumulation.
"""

import numpy as np

from config.settings import (
    iron_half_life_days,
    ferritin_steady_state,
    iron_absorption_fraction,
    ferritin_threshold,
)


def compute_ferritin_accumulation(time_days, baseline_ferritin,
                                   steady_state, half_life):
    """
    first-order exponential accumulation of ferritin.
    c(t) = c_ss - (c_ss - c_0) * exp(-k * t)
    ref: sim et al. (2019), european journal of applied physiology.
    """
    k_elim = np.log(2) / half_life
    trajectory = steady_state - (steady_state - baseline_ferritin) * np.exp(-k_elim * time_days)
    return trajectory


def compute_iron_absorption(dose_mg, bioavailability_fraction):
    """
    actual absorbed iron from oral supplementation.
    ref: sim et al. (2019) — absorption fraction typically 10%.
    """
    absorbed = dose_mg * bioavailability_fraction
    return absorbed


def compute_transferrin_saturation(serum_iron, tibc):
    """
    transferrin saturation percentage.
    """
    if tibc <= 0:
        return 0.0
    saturation = (serum_iron / tibc) * 100.0
    return round(saturation, 2)


def simulate_iron_kinetics(time_days_array, baseline_ferritin,
                            steady_state, half_life, daily_supplement_mg=0):
    """
    simulates ferritin trajectory over time with optional supplementation.
    ref: project plan — multi-compartment pk model.
    """
    if daily_supplement_mg > 0:
        absorbed_daily = compute_iron_absorption(daily_supplement_mg, iron_absorption_fraction)
        adjusted_steady_state = steady_state + absorbed_daily * 0.5
    else:
        adjusted_steady_state = steady_state

    trajectory = compute_ferritin_accumulation(
        time_days_array, baseline_ferritin, adjusted_steady_state, half_life
    )

    days_to_threshold = None
    for i, val in enumerate(trajectory):
        if val >= ferritin_threshold and baseline_ferritin < ferritin_threshold:
            days_to_threshold = int(time_days_array[i])
            break

    final_ferritin = float(trajectory[-1])
    is_sufficient = final_ferritin >= ferritin_threshold

    result = {
        "algorithm": "iron_kinetics",
        "time_days": time_days_array.tolist(),
        "ferritin_trajectory": np.round(trajectory, 2).tolist(),
        "baseline_ferritin": baseline_ferritin,
        "final_ferritin": round(final_ferritin, 2),
        "is_sufficient": is_sufficient,
        "days_to_threshold": days_to_threshold,
        "threshold": ferritin_threshold,
    }
    return result


def run_iron_kinetics(bloodwork):
    """
    runs iron kinetics from bloodwork panel data.
    """
    iron_panel = bloodwork["iron_panel"]
    baseline_ferritin = iron_panel["serum_ferritin_ng_ml"]

    time_days = np.arange(0, 91, 1)

    supplement_mg = 0
    if baseline_ferritin < ferritin_threshold:
        supplement_mg = 65

    result = simulate_iron_kinetics(
        time_days_array=time_days,
        baseline_ferritin=baseline_ferritin,
        steady_state=ferritin_steady_state,
        half_life=iron_half_life_days,
        daily_supplement_mg=supplement_mg,
    )

    serum_iron = iron_panel.get("serum_iron_ug_dl", 100.0)
    tibc = iron_panel.get("tibc_ug_dl", 300.0)
    result["transferrin_saturation"] = compute_transferrin_saturation(
        serum_iron,
        tibc,
    )

    return result
