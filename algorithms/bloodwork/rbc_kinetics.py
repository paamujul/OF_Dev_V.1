"""
red blood cell pharmacodynamic kinetics model.
ref: wada standard — rbc lifespan 120 days.
ref: project plan flowchart — rbc growth via bone marrow vs destruction rate.
"""

import numpy as np

from config.settings import (
    rbc_lifespan_days,
    rbc_normal_count,
    epo_normal,
    rbc_production_rate,
)


def compute_rbc_production(epo_concentration, current_rbc):
    """
    bone marrow rbc production driven by epo concentration.
    ref: wada standard.
    """
    epo_ratio = epo_concentration / epo_normal
    production = rbc_production_rate * epo_ratio * (1.0 - current_rbc / (rbc_normal_count * 1.2))
    return max(0.0, production)


def compute_rbc_destruction(current_rbc):
    """
    rbc destruction at fixed lifespan rate of 1/120 days.
    ref: wada standard.
    """
    destruction = current_rbc / rbc_lifespan_days
    return destruction


def simulate_rbc_kinetics(time_steps_days, initial_rbc, epo_concentration_array):
    """
    simulates rbc count over time using euler integration.
    ref: project plan — pharmacodynamics (pd) model.
    """
    n_steps = len(time_steps_days)
    rbc_trajectory = np.zeros(n_steps)
    rbc_trajectory[0] = initial_rbc

    for i in range(1, n_steps):
        dt = time_steps_days[i] - time_steps_days[i - 1]
        current_rbc = rbc_trajectory[i - 1]
        epo = epo_concentration_array[min(i, len(epo_concentration_array) - 1)]

        production = compute_rbc_production(epo, current_rbc)
        destruction = compute_rbc_destruction(current_rbc)

        delta = (production - destruction) * dt
        rbc_trajectory[i] = max(0.0, current_rbc + delta)

    final_rbc = rbc_trajectory[-1]
    is_within_normal = 4.5 <= final_rbc <= 5.5

    result = {
        "algorithm": "rbc_kinetics",
        "time_days": time_steps_days.tolist(),
        "rbc_trajectory": np.round(rbc_trajectory, 4).tolist(),
        "initial_rbc": initial_rbc,
        "final_rbc": round(float(final_rbc), 4),
        "is_within_normal_range": is_within_normal,
        "normal_range": {"low": 4.5, "high": 5.5},
    }
    return result


def run_rbc_kinetics(bloodwork):
    """
    runs rbc kinetics using bloodwork panel data.
    """
    initial_rbc = bloodwork["cbc"]["rbc_count_million_per_ul"]
    epo_value = bloodwork.get("epo", {}).get("epo_miu_ml", epo_normal)

    time_steps = np.arange(0, 91, 1)
    epo_array = np.full(len(time_steps), epo_value)

    return simulate_rbc_kinetics(time_steps, initial_rbc, epo_array)
