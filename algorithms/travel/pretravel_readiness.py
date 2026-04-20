"""
pre-travel readiness score — multiplicative attenuation model.
ref: plews et al. (2013), buchheit (2014), fullagar et al. (2015),
     hayes et al. (2015), brancaccio et al. (2007), sim et al. (2019),
     waterhouse et al. (2007).
"""

import math
import statistics

from config.settings import (
    w_ans,
    w_slp,
    z_hrv_optimal_low,
    z_hrv_optimal_high,
    z_hrv_hyperactivity,
    ans_penalty_per_z,
    ans_hyperactivity_cap,
    sleep_tst_cap,
    ftc_deficit_threshold,
    rho_hormonal_penalty,
    ferritin_threshold,
    rho_iron_penalty,
    ck_threshold,
    hscrp_threshold,
    rho_muscle_penalty,
    k_tz_east,
    k_tz_west,
    k_alt,
    altitude_threshold,
)


def compute_ans_readiness(hrv_history):
    """
    autonomic readiness via ln(rmssd) z-score.
    ref: plews et al. (2013), sports medicine.
    ref: buchheit (2014), frontiers in physiology.
    """
    ln_values = [math.log(v) for v in hrv_history]
    mean_ln = statistics.mean(ln_values)
    std_ln = statistics.stdev(ln_values)

    if std_ln == 0:
        return 100.0

    current_ln = ln_values[-1]
    z_hrv = (current_ln - mean_ln) / std_ln

    if z_hrv_optimal_low <= z_hrv <= z_hrv_optimal_high:
        phi_ans = 100.0
    elif z_hrv < z_hrv_optimal_low:
        phi_ans = 100.0 - (ans_penalty_per_z * abs(z_hrv))
    elif z_hrv > z_hrv_hyperactivity:
        phi_ans = ans_hyperactivity_cap
    else:
        phi_ans = 100.0 - (ans_penalty_per_z * (z_hrv - z_hrv_optimal_high))

    phi_ans = max(0.0, min(100.0, phi_ans))
    return phi_ans


def compute_sleep_readiness(sleep_efficiency, total_sleep_time):
    """
    sleep readiness from efficiency and total sleep time.
    ref: fullagar et al. (2015), sports medicine.
    """
    se_fraction = sleep_efficiency / 100.0
    tst_fraction = min(total_sleep_time, sleep_tst_cap) / sleep_tst_cap
    phi_slp = se_fraction * tst_fraction * 100.0
    return max(0.0, min(100.0, phi_slp))


def compute_biochemical_attenuation(bloodwork):
    """
    biochemical attenuation factor (omega_bio) via multiplicative penalties.
    ref: hayes et al. (2015), sim et al. (2019), brancaccio et al. (2007).
    """
    hormonal = bloodwork.get("hormonal_panel", {})
    ft_ratio = hormonal.get("ft_cortisol_ratio", 1.0)
    ft_baseline = hormonal.get("ft_cortisol_ratio_baseline", 1.0)

    if ft_baseline > 0:
        ratio_drop = (ft_baseline - ft_ratio) / ft_baseline
    else:
        ratio_drop = 0.0

    if ratio_drop > ftc_deficit_threshold:
        rho_h = rho_hormonal_penalty
    else:
        rho_h = 1.0

    iron = bloodwork.get("iron_panel", {})
    ferritin = iron.get("serum_ferritin_ng_ml", 100.0)

    if ferritin < ferritin_threshold:
        rho_i = rho_iron_penalty
    else:
        rho_i = 1.0

    inflammatory = bloodwork.get("inflammatory_recovery", {})
    ck = inflammatory.get("creatine_kinase_u_l", 0.0)
    hscrp = inflammatory.get("hscrp_mg_l", 0.0)

    if ck > ck_threshold and hscrp > hscrp_threshold:
        rho_m = rho_muscle_penalty
    else:
        rho_m = 1.0

    omega_bio = min(1.0, rho_h) * min(1.0, rho_i) * min(1.0, rho_m)

    details = {
        "rho_hormonal": rho_h,
        "rho_iron": rho_i,
        "rho_muscle": rho_m,
        "omega_bio": omega_bio,
    }
    return omega_bio, details


def compute_environmental_friction(timezone_shift, direction, altitude_delta):
    """
    environmental friction factor (lambda_env).
    ref: waterhouse et al. (2007), journal of sports sciences.
    """
    if direction == "east":
        tz_coeff = k_tz_east
    else:
        tz_coeff = k_tz_west

    tz_penalty = tz_coeff * timezone_shift

    if altitude_delta > altitude_threshold:
        alt_penalty = k_alt * altitude_delta
    else:
        alt_penalty = 0.0

    lambda_env = 1.0 - (tz_penalty + alt_penalty)
    lambda_env = max(0.0, min(1.0, lambda_env))

    details = {
        "tz_penalty": tz_penalty,
        "alt_penalty": alt_penalty,
        "lambda_env": lambda_env,
    }
    return lambda_env, details


def compute_pretravel_score(athlete):
    """
    master pre-travel readiness score (r_total).
    r_total = [(w_ans * phi_ans) + (w_slp * phi_slp)] * omega_bio * lambda_env
    ref: project plan doc 1 — multiplicative attenuation model.
    """
    hrv_history = athlete.wearables["hrv_rmssd_30d"]
    phi_ans = compute_ans_readiness(hrv_history)

    sleep_eff = athlete.avg_sleep_efficiency()
    sleep_tst = athlete.avg_total_sleep_time()
    phi_slp = compute_sleep_readiness(sleep_eff, sleep_tst)

    omega_bio, bio_details = compute_biochemical_attenuation(athlete.bloodwork)

    tz_shift = athlete.timezone_shift()
    direction = athlete.direction()
    alt_delta = athlete.altitude_delta()
    lambda_env, env_details = compute_environmental_friction(
        tz_shift, direction, alt_delta
    )

    wearable_baseline = (w_ans * phi_ans) + (w_slp * phi_slp)
    r_total = wearable_baseline * omega_bio * lambda_env

    result = {
        "algorithm": "pretravel_readiness",
        "r_total": round(r_total, 2),
        "wearable_baseline": round(wearable_baseline, 2),
        "phi_ans": round(phi_ans, 2),
        "phi_slp": round(phi_slp, 2),
        "omega_bio": round(omega_bio, 4),
        "lambda_env": round(lambda_env, 4),
        "biochemical_details": bio_details,
        "environmental_details": env_details,
    }
    return result
