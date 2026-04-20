"""
inflammatory marker kinetics via the bateman function.
ref: brancaccio et al. (2007), british medical bulletin — ck as marker.
ref: project plan flowchart — impulse-response of ck leakage.
"""

import numpy as np

from config.settings import (
    ck_appearance_rate,
    ck_elimination_rate,
    ck_volume_distribution,
    ck_threshold,
    hscrp_threshold,
)


def bateman_function(time_array, dose, ka, ke, vd):
    """
    bateman equation for impulse-response pharmacokinetics.
    c(t) = (dose * ka) / (vd * (ka - ke)) * (exp(-ke * t) - exp(-ka * t))
    ref: brancaccio et al. (2007), british medical bulletin.
    """
    if abs(ka - ke) < 1e-10:
        ke_adj = ke * 0.99
    else:
        ke_adj = ke

    coefficient = (dose * ka) / (vd * (ka - ke_adj))
    concentration = coefficient * (np.exp(-ke_adj * time_array) - np.exp(-ka * time_array))
    concentration = np.maximum(concentration, 0.0)

    return concentration


def compute_peak_time(ka, ke):
    """
    time to peak concentration (tmax).
    tmax = ln(ka/ke) / (ka - ke)
    """
    if abs(ka - ke) < 1e-10:
        return 0.0
    if ka <= 0 or ke <= 0:
        return 0.0

    tmax = np.log(ka / ke) / (ka - ke)
    return max(0.0, float(tmax))


def compute_peak_concentration(dose, ka, ke, vd):
    """
    concentration at tmax.
    """
    tmax = compute_peak_time(ka, ke)
    if tmax == 0:
        return 0.0
    peak = bateman_function(np.array([tmax]), dose, ka, ke, vd)
    return float(peak[0])


def simulate_inflammation_kinetics(time_hours, muscle_damage_dose,
                                    ka, ke, vd, baseline_ck=0):
    """
    simulates ck impulse-response following muscle damage.
    ref: project plan — bateman function mapping ck leakage against renal clearance.
    """
    time_array = np.array(time_hours) if not isinstance(time_hours, np.ndarray) else time_hours

    ck_response = bateman_function(time_array, muscle_damage_dose, ka, ke, vd)
    ck_total = ck_response + baseline_ck

    tmax = compute_peak_time(ka, ke)
    peak_ck = compute_peak_concentration(muscle_damage_dose, ka, ke, vd) + baseline_ck

    exceeds_threshold = peak_ck > ck_threshold

    clearance_time = None
    for i, val in enumerate(ck_total):
        if i > 0 and val < ck_threshold and ck_total[i - 1] >= ck_threshold:
            clearance_time = round(float(time_array[i]), 1)
            break

    result = {
        "algorithm": "inflammation_kinetics",
        "time_hours": time_array.tolist(),
        "ck_trajectory": np.round(ck_total, 2).tolist(),
        "baseline_ck": baseline_ck,
        "peak_ck": round(peak_ck, 2),
        "time_to_peak_hours": round(tmax, 2),
        "exceeds_threshold": exceeds_threshold,
        "threshold": ck_threshold,
        "clearance_time_hours": clearance_time,
    }
    return result


def assess_recovery_status(ck_level, hscrp_level):
    """
    combined ck and hs-crp assessment for muscle damage status.
    ref: brancaccio et al. (2007) — ck > 500 u/l + hs-crp > 3 mg/l.
    """
    if ck_level > ck_threshold and hscrp_level > hscrp_threshold:
        status = "unresolved_sarcomere_damage"
        recovery_ready = False
    elif ck_level > ck_threshold:
        status = "elevated_muscle_damage"
        recovery_ready = False
    elif hscrp_level > hscrp_threshold:
        status = "systemic_inflammation"
        recovery_ready = False
    else:
        status = "recovered"
        recovery_ready = True

    return {
        "status": status,
        "recovery_ready": recovery_ready,
        "ck_level": ck_level,
        "hscrp_level": hscrp_level,
    }


def run_inflammation_kinetics(bloodwork):
    """
    runs inflammation kinetics from bloodwork data.
    """
    inflammatory = bloodwork["inflammatory_recovery"]
    baseline_ck = inflammatory["creatine_kinase_u_l"]
    hscrp = inflammatory["hscrp_mg_l"]

    time_hours = np.arange(0, 97, 1)

    simulated_damage_dose = baseline_ck * ck_volume_distribution

    simulation = simulate_inflammation_kinetics(
        time_hours=time_hours,
        muscle_damage_dose=simulated_damage_dose,
        ka=ck_appearance_rate,
        ke=ck_elimination_rate,
        vd=ck_volume_distribution,
        baseline_ck=baseline_ck * 0.3,
    )

    recovery = assess_recovery_status(baseline_ck, hscrp)
    simulation["recovery_status"] = recovery

    return simulation
