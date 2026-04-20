"""
hormonal panel kinetics via hill equation negative feedback.
ref: hayes et al. (2015), chronobiology international — cortisol/testosterone.
ref: project plan flowchart — negative feedback control systems.
"""

import numpy as np

from config.settings import (
    max_secretion_rate,
    threshold_kd,
    hill_coefficient,
    clearance_rate,
    ftc_deficit_threshold,
)


def hill_secretion_rate(concentration, vmax, kd, n):
    """
    hill equation for receptor-mediated negative feedback.
    rate = vmax * kd^n / (kd^n + c^n)
    ref: hayes et al. (2015), chronobiology international.
    """
    numerator = vmax * (kd ** n)
    denominator = (kd ** n) + (concentration ** n)
    if denominator == 0:
        return 0.0
    rate = numerator / denominator
    return rate


def compute_clearance(concentration, k_clear):
    """
    first-order clearance of hormone from circulation.
    """
    return k_clear * concentration


def simulate_hormone_kinetics(time_steps, initial_concentration, vmax,
                               kd, n, k_clear, dt=1.0):
    """
    euler integration of hormone dynamics with hill feedback.
    ref: project plan flowchart — hill equation.
    """
    n_steps = len(time_steps)
    trajectory = np.zeros(n_steps)
    trajectory[0] = initial_concentration

    for i in range(1, n_steps):
        current = trajectory[i - 1]
        secretion = hill_secretion_rate(current, vmax, kd, n)
        elimination = compute_clearance(current, k_clear)
        delta = (secretion - elimination) * dt
        trajectory[i] = max(0.0, current + delta)

    steady_state_approx = trajectory[-1]

    result = {
        "algorithm": "hormone_kinetics",
        "time_steps": time_steps.tolist(),
        "concentration_trajectory": np.round(trajectory, 4).tolist(),
        "initial_concentration": initial_concentration,
        "steady_state_approx": round(float(steady_state_approx), 4),
        "parameters": {
            "vmax": vmax,
            "kd": kd,
            "hill_coefficient": n,
            "clearance_rate": k_clear,
        },
    }
    return result


def compute_ftc_ratio_status(ft_ratio_current, ft_ratio_baseline):
    """
    evaluates free testosterone to cortisol ratio deficit.
    ref: hayes et al. (2015) — >30% drop indicates catabolic state.
    """
    if ft_ratio_baseline <= 0:
        return {"status": "insufficient_data", "deficit_percent": 0.0}

    deficit = (ft_ratio_baseline - ft_ratio_current) / ft_ratio_baseline

    if deficit > ftc_deficit_threshold:
        status = "catabolic_state"
    elif deficit > 0.15:
        status = "elevated_stress"
    else:
        status = "normal"

    return {
        "status": status,
        "deficit_percent": round(deficit * 100, 2),
        "threshold_percent": ftc_deficit_threshold * 100,
    }


def run_hormone_kinetics(bloodwork):
    """
    runs hormone kinetics simulation from bloodwork data.
    """
    hormonal = bloodwork["hormonal_panel"]

    time_steps = np.arange(0, 49, 1)

    testosterone_result = simulate_hormone_kinetics(
        time_steps=time_steps,
        initial_concentration=hormonal["free_testosterone_pg_ml"],
        vmax=max_secretion_rate,
        kd=threshold_kd,
        n=hill_coefficient,
        k_clear=clearance_rate,
    )
    testosterone_result["marker"] = "free_testosterone"

    cortisol_result = simulate_hormone_kinetics(
        time_steps=time_steps,
        initial_concentration=hormonal["cortisol_ug_dl"],
        vmax=max_secretion_rate * 0.8,
        kd=threshold_kd * 0.6,
        n=hill_coefficient,
        k_clear=clearance_rate * 1.5,
    )
    cortisol_result["marker"] = "cortisol"

    ftc_status = compute_ftc_ratio_status(
        hormonal["ft_cortisol_ratio"],
        hormonal["ft_cortisol_ratio_baseline"],
    )

    result = {
        "algorithm": "hormone_kinetics",
        "testosterone": testosterone_result,
        "cortisol": cortisol_result,
        "ftc_ratio_status": ftc_status,
    }
    return result
