"""
pre-travel readiness score — multiplicative attenuation model.
ref: plews et al. (2013), sports medicine — hrv baseline z-score.
ref: buchheit (2014), frontiers in physiology — ans combined readiness.
ref: miller et al. (2020), bmj open sport & exercise medicine — rr telemetry.
ref: fullagar et al. (2015), sports medicine — sleep efficiency.
ref: simpson et al. (2017), scand j med sci sports — sleep debt.
ref: kellmann et al. (2018), ijspp — sleep architecture.
ref: hayes et al. (2015), brancaccio et al. (2007), sim et al. (2019).
ref: waterhouse et al. (2007), journal of sports sciences.
"""

import math
import statistics

from config.settings import (
    w_ans,
    w_slp,
    z_hrv_optimal_low,
    z_hrv_optimal_high,
    z_hrv_hyperactivity_threshold,
    z_rhr_hyperactivity_threshold,
    hyperactivity_cap,
    ans_hrv_penalty_weight,
    ans_rhr_penalty_weight,
    ans_rr_penalty_weight,
    sleep_tst_cap,
    sleep_debt_threshold_hours,
    sleep_debt_penalty,
    deep_rem_minimum_percent,
    architecture_penalty,
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


def compute_ans_readiness(hrv_history, rhr_history, rr_history):
    """
    upgraded autonomic readiness via multi-signal z-scores.
    integrates hrv, resting heart rate, and respiratory rate.
    ref: plews et al. (2013), buchheit (2014), miller et al. (2020).
    """
    ln_values = [math.log(v) for v in hrv_history]
    mean_ln = statistics.mean(ln_values)
    std_ln = statistics.stdev(ln_values)

    if std_ln == 0:
        z_hrv = 0.0
    else:
        current_ln = ln_values[-1]
        z_hrv = (current_ln - mean_ln) / std_ln

    rhr_mean = statistics.mean(rhr_history)
    rhr_std = statistics.stdev(rhr_history)

    if rhr_std == 0:
        z_rhr = 0.0
    else:
        z_rhr = (rhr_history[-1] - rhr_mean) / rhr_std

    rr_mean = statistics.mean(rr_history)
    rr_std = statistics.stdev(rr_history)

    if rr_std == 0:
        z_rr = 0.0
    else:
        z_rr = (rr_history[-1] - rr_mean) / rr_std

    hrv_penalty = ans_hrv_penalty_weight * abs(min(0, z_hrv))
    rhr_penalty = ans_rhr_penalty_weight * max(0, z_rhr)
    rr_penalty = ans_rr_penalty_weight * max(0, z_rr)

    phi_ans = 100.0 - (hrv_penalty + rhr_penalty + rr_penalty)

    if z_hrv > z_hrv_hyperactivity_threshold and z_rhr < z_rhr_hyperactivity_threshold:
        phi_ans = min(phi_ans, hyperactivity_cap)

    phi_ans = max(0.0, min(100.0, phi_ans))
    return phi_ans, {"z_hrv": round(z_hrv, 3), "z_rhr": round(z_rhr, 3), "z_rr": round(z_rr, 3)}


def compute_sleep_readiness(sleep_efficiency, total_sleep_time,
                            sleep_debt, deep_rem_percent):
    """
    upgraded sleep readiness with debt and architecture modifiers.
    ref: fullagar et al. (2015), simpson et al. (2017), kellmann et al. (2018).
    """
    se_fraction = sleep_efficiency / 100.0
    tst_fraction = min(total_sleep_time, sleep_tst_cap) / sleep_tst_cap

    if sleep_debt > sleep_debt_threshold_hours:
        gamma_debt = sleep_debt_penalty
    else:
        gamma_debt = 1.0

    if deep_rem_percent < deep_rem_minimum_percent:
        gamma_stages = architecture_penalty
    else:
        gamma_stages = 1.0

    phi_slp = se_fraction * tst_fraction * gamma_debt * gamma_stages * 100.0

    details = {
        "gamma_debt": gamma_debt,
        "gamma_stages": gamma_stages,
        "deep_rem_percent": round(deep_rem_percent, 1),
        "sleep_debt_hours": round(sleep_debt, 2),
    }
    return max(0.0, min(100.0, phi_slp)), details


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
    ref: project plan doc 1 — upgraded multiplicative attenuation model.
    """
    hrv_history = athlete.wearables["hrv_rmssd_30d"]
    rhr_history = athlete.wearables["resting_hr_7d"]
    rr_history = athlete.wearables["respiratory_rate_7d"]

    phi_ans, ans_details = compute_ans_readiness(hrv_history, rhr_history, rr_history)

    sleep_eff = athlete.avg_sleep_efficiency()
    sleep_tst = athlete.avg_total_sleep_time()
    sleep_debt = athlete.sleep_debt()
    deep_rem = athlete.avg_deep_rem_percent()
    phi_slp, slp_details = compute_sleep_readiness(sleep_eff, sleep_tst, sleep_debt, deep_rem)

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
        "ans_details": ans_details,
        "sleep_details": slp_details,
        "omega_bio": round(omega_bio, 4),
        "lambda_env": round(lambda_env, 4),
        "biochemical_details": bio_details,
        "environmental_details": env_details,
    }
    return result
