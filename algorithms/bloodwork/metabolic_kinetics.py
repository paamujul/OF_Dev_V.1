"""
metabolic kinetics via bergman minimal model for glucose disposal.
ref: project plan flowchart — bergman minimal model.
"""

import numpy as np

from config.settings import (
    basal_glucose,
    independent_clearance_p1,
    insulin_sensitivity_p3,
)


def compute_glucose_change(glucose, insulin_action, p1, gb):
    """
    glucose rate of change from bergman minimal model.
    dg/dt = -p1 * (g - gb) - x * g
    ref: project plan — fractional drops of glucose independent of basal resistance.
    """
    dg = -p1 * (glucose - gb) - insulin_action * glucose
    return dg


def compute_insulin_action_change(insulin_action, insulin, p2, p3):
    """
    insulin action rate of change.
    dx/dt = -p2 * x + p3 * (i - ib)
    """
    ib = 5.0
    dx = -p2 * insulin_action + p3 * max(0, insulin - ib)
    return dx


def simulate_metabolic_kinetics(time_minutes, initial_glucose, gb,
                                 insulin_array, p1, p3, p2=0.025):
    """
    simulates glucose trajectory post-meal using bergman minimal model.
    ref: project plan — bergman minimal model determines efficiency
    of carbohydrate disposal.
    """
    n_steps = len(time_minutes)
    glucose_trajectory = np.zeros(n_steps)
    insulin_action_trajectory = np.zeros(n_steps)

    glucose_trajectory[0] = initial_glucose
    insulin_action_trajectory[0] = 0.0

    for i in range(1, n_steps):
        dt = time_minutes[i] - time_minutes[i - 1]
        g = glucose_trajectory[i - 1]
        x = insulin_action_trajectory[i - 1]
        ins = insulin_array[min(i, len(insulin_array) - 1)]

        dg = compute_glucose_change(g, x, p1, gb)
        dx = compute_insulin_action_change(x, ins, p2, p3)

        glucose_trajectory[i] = max(0.0, g + dg * dt)
        insulin_action_trajectory[i] = max(0.0, x + dx * dt)

    time_to_baseline = None
    for i in range(1, n_steps):
        if glucose_trajectory[i] <= gb * 1.05 and glucose_trajectory[i - 1] > gb * 1.05:
            time_to_baseline = int(time_minutes[i])
            break

    peak_glucose = float(np.max(glucose_trajectory))
    peak_time = int(time_minutes[np.argmax(glucose_trajectory)])

    glucose_auc = float(np.trapz(glucose_trajectory - gb, time_minutes))

    si = p3 / p2 if p2 > 0 else 0.0

    result = {
        "algorithm": "metabolic_kinetics",
        "time_minutes": time_minutes.tolist(),
        "glucose_trajectory": np.round(glucose_trajectory, 2).tolist(),
        "insulin_action_trajectory": np.round(insulin_action_trajectory, 6).tolist(),
        "initial_glucose": initial_glucose,
        "basal_glucose": gb,
        "peak_glucose": round(peak_glucose, 2),
        "peak_time_minutes": peak_time,
        "time_to_baseline_minutes": time_to_baseline,
        "glucose_auc": round(glucose_auc, 2),
        "insulin_sensitivity_index": round(si, 6),
    }
    return result


def generate_insulin_response(time_minutes, peak_insulin, time_to_peak=30):
    """
    generates a synthetic insulin response curve for simulation.
    models the typical post-prandial insulin spike and decay.
    """
    insulin = np.zeros(len(time_minutes))
    basal_insulin = 5.0

    for i, t in enumerate(time_minutes):
        if t <= time_to_peak:
            insulin[i] = basal_insulin + (peak_insulin - basal_insulin) * (t / time_to_peak)
        else:
            decay_constant = 0.02
            insulin[i] = basal_insulin + (peak_insulin - basal_insulin) * np.exp(
                -decay_constant * (t - time_to_peak)
            )

    return insulin


def run_metabolic_kinetics(bloodwork):
    """
    runs metabolic kinetics from bloodwork panel data.
    """
    metabolic = bloodwork["metabolic_panel"]
    fasting_glucose = metabolic["fasting_glucose_mg_dl"]
    fasting_insulin = metabolic["fasting_insulin_uiu_ml"]

    time_minutes = np.arange(0, 181, 1)

    postprandial_glucose = fasting_glucose * 1.6
    peak_insulin = fasting_insulin * 8

    insulin_curve = generate_insulin_response(time_minutes, peak_insulin)

    result = simulate_metabolic_kinetics(
        time_minutes=time_minutes,
        initial_glucose=postprandial_glucose,
        gb=basal_glucose,
        insulin_array=insulin_curve,
        p1=independent_clearance_p1,
        p3=insulin_sensitivity_p3,
    )

    homa_ir = (fasting_glucose * fasting_insulin) / 405.0
    result["homa_ir"] = round(homa_ir, 3)
    result["hba1c"] = metabolic.get("hba1c_percent", None)

    return result
