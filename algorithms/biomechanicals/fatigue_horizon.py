"""
systemic delivery & technique degradation simulator (fatigue horizon).
predicts the number of maximal repetitions before cns-enforced technique failure.
ref: noakes (2012), sports medicine — central governor model.
ref: amann & calbet (2008), journal of applied physiology — o2 transport.
ref: peeling et al. (2008) — iron and exercise performance.
ref: mairbäurl (2013), frontiers in physiology — rbc in sport.
ref: nybo (2008), progress in neurobiology — brain temperature and fatigue.
"""

import statistics

from config.settings import (
    fatigue_ferritin_weight,
    fatigue_rbc_weight,
    fatigue_hba1c_weight,
    fatigue_spo2_weight,
    fatigue_cardio_weight,
    fatigue_ferritin_optimal,
    fatigue_ferritin_critical,
    fatigue_rbc_low,
    fatigue_rbc_high,
    fatigue_epo_elevated,
    fatigue_hba1c_optimal,
    fatigue_hba1c_impaired,
    fatigue_spo2_optimal,
    fatigue_spo2_critical,
    fatigue_rhr_elevated_bpm,
    fatigue_rr_elevated,
    fatigue_baseline_reps,
    fatigue_min_reps,
)


def compute_iron_delivery_penalty(ferritin, tibc):
    """
    ferritin and tibc as limiting factors for oxidative enzyme function.
    ref: peeling et al. (2008) — iron depletion and peripheral fatigue.
    """
    if ferritin >= fatigue_ferritin_optimal:
        ferritin_penalty = 0.0
    elif ferritin >= fatigue_ferritin_critical:
        f_range = fatigue_ferritin_optimal - fatigue_ferritin_critical
        f_deficit = fatigue_ferritin_optimal - ferritin
        ferritin_penalty = f_deficit / f_range
    else:
        ferritin_penalty = 1.0

    tibc_saturation = 1.0 - min(1.0, max(0.0, (tibc - 250) / 200))
    combined = ferritin_penalty * 0.7 + tibc_saturation * 0.3

    details = {
        "serum_ferritin_ng_ml": ferritin,
        "tibc_ug_dl": tibc,
        "tibc_saturation_index": round(tibc_saturation, 3),
    }
    return combined, details


def compute_rbc_delivery_penalty(rbc_count, epo_level):
    """
    total oxygen-carrying capacity.
    elevated epo suggests hypoxic stress and upregulation attempt.
    ref: mairbäurl (2013), frontiers in physiology.
    """
    if fatigue_rbc_low <= rbc_count <= fatigue_rbc_high:
        rbc_penalty = 0.0
    elif rbc_count < fatigue_rbc_low:
        rbc_penalty = min(1.0, (fatigue_rbc_low - rbc_count) / 1.0)
    else:
        rbc_penalty = 0.0

    if epo_level > fatigue_epo_elevated:
        epo_stress = min(1.0, (epo_level - fatigue_epo_elevated) / 10.0)
    else:
        epo_stress = 0.0

    combined = rbc_penalty * 0.6 + epo_stress * 0.4

    details = {
        "rbc_count_million_per_ul": rbc_count,
        "epo_miu_ml": epo_level,
        "epo_stress_flag": epo_level > fatigue_epo_elevated,
    }
    return combined, details


def compute_hba1c_penalty(hba1c):
    """
    glycated hemoglobin impairs oxygen offloading at tissue level.
    ref: mairbäurl (2013) — rightward bohr effect shift.
    """
    if hba1c <= fatigue_hba1c_optimal:
        penalty = 0.0
    elif hba1c <= fatigue_hba1c_impaired:
        hba1c_range = fatigue_hba1c_impaired - fatigue_hba1c_optimal
        hba1c_excess = hba1c - fatigue_hba1c_optimal
        penalty = hba1c_excess / hba1c_range
    else:
        penalty = 1.0

    return penalty, {"hba1c_percent": hba1c}


def compute_realtime_spo2_penalty(spo2_avg):
    """
    spo2 telemetry monitoring oxygen debt accumulation.
    ref: amann & calbet (2008) — arterial o2 regulates central motor drive.
    """
    if spo2_avg >= fatigue_spo2_optimal:
        penalty = 0.0
    elif spo2_avg >= fatigue_spo2_critical:
        spo2_range = fatigue_spo2_optimal - fatigue_spo2_critical
        spo2_drop = fatigue_spo2_optimal - spo2_avg
        penalty = spo2_drop / spo2_range
    else:
        penalty = 1.0

    return penalty, {"spo2_avg": round(spo2_avg, 1)}


def compute_cardiorespiratory_penalty(resting_hr, respiratory_rate, session_duration):
    """
    cardiorespiratory strain from rhr, respiratory rate, and duration.
    ref: noakes (2012) — central governor anticipatory regulation.
    """
    rhr_penalty = 0.0
    if resting_hr > fatigue_rhr_elevated_bpm:
        rhr_penalty = min(1.0, (resting_hr - fatigue_rhr_elevated_bpm) / 15.0)

    rr_penalty = 0.0
    if respiratory_rate > fatigue_rr_elevated:
        rr_penalty = min(1.0, (respiratory_rate - fatigue_rr_elevated) / 5.0)

    duration_factor = min(1.0, session_duration / 120.0) * 0.3

    combined = (rhr_penalty * 0.4 + rr_penalty * 0.3 + duration_factor)

    details = {
        "resting_hr_bpm": resting_hr,
        "respiratory_rate": round(respiratory_rate, 1),
        "session_duration_minutes": session_duration,
    }
    return min(1.0, combined), details


def compute_hmm_state(composite_penalty):
    """
    hidden markov model state classification.
    s1 = optimal, s2 = compensatory, s3 = degraded.
    transition probabilities weighted by composite oxygen delivery.
    """
    if composite_penalty < 0.3:
        state = "s1_optimal"
        transition_risk = "low"
    elif composite_penalty < 0.6:
        state = "s2_compensatory"
        transition_risk = "moderate"
    else:
        state = "s3_degraded"
        transition_risk = "high"

    p_s1_to_s2 = min(1.0, composite_penalty * 1.5)
    p_s2_to_s3 = min(1.0, max(0.0, (composite_penalty - 0.3) * 2.0))

    return {
        "current_state": state,
        "transition_risk": transition_risk,
        "p_s1_to_s2": round(p_s1_to_s2, 3),
        "p_s2_to_s3": round(p_s2_to_s3, 3),
    }


def compute_fatigue_horizon(athlete):
    """
    master fatigue horizon function.
    predicts number of maximal reps before technique failure.
    """
    iron_panel = athlete.bloodwork.get("iron_panel", {})
    ferritin = iron_panel.get("serum_ferritin_ng_ml", fatigue_ferritin_optimal)
    tibc = iron_panel.get("tibc_ug_dl", 320.0)
    iron_penalty, iron_details = compute_iron_delivery_penalty(ferritin, tibc)

    cbc = athlete.bloodwork.get("cbc", {})
    rbc = cbc.get("rbc_count_million_per_ul", 5.0)
    epo = athlete.bloodwork.get("epo", {}).get("epo_miu_ml", 10.0)
    rbc_penalty, rbc_details = compute_rbc_delivery_penalty(rbc, epo)

    metabolic = athlete.bloodwork.get("metabolic_panel", {})
    hba1c = metabolic.get("hba1c_percent", fatigue_hba1c_optimal)
    hba1c_penalty, hba1c_details = compute_hba1c_penalty(hba1c)

    spo2_avg = athlete.avg_spo2()
    spo2_penalty, spo2_details = compute_realtime_spo2_penalty(spo2_avg)

    resting_hr = athlete.resting_hr_mean()
    respiratory_rate = athlete.avg_respiratory_rate()
    session_dur = athlete.session_duration()
    cardio_penalty, cardio_details = compute_cardiorespiratory_penalty(
        resting_hr, respiratory_rate, session_dur
    )

    composite = (
        fatigue_ferritin_weight * iron_penalty
        + fatigue_rbc_weight * rbc_penalty
        + fatigue_hba1c_weight * hba1c_penalty
        + fatigue_spo2_weight * spo2_penalty
        + fatigue_cardio_weight * cardio_penalty
    )

    hmm_state = compute_hmm_state(composite)

    rep_range = fatigue_baseline_reps - fatigue_min_reps
    predicted_reps = fatigue_baseline_reps - (composite * rep_range)
    predicted_reps = max(fatigue_min_reps, round(predicted_reps))

    if predicted_reps <= 5:
        severity = "critical"
        constraint = (
            f"terminate session at {predicted_reps} maximal efforts — "
            "tissue-level hypoxia triggering central motor inhibition. "
            "technical degradation guaranteed beyond this point"
        )
    elif predicted_reps <= 8:
        severity = "restricted"
        constraint = (
            f"limit to {predicted_reps} maximal efforts — "
            "oxygen delivery compromised, premature elbow drop likely"
        )
    else:
        severity = "normal"
        constraint = f"up to {predicted_reps} maximal efforts available"

    result = {
        "algorithm": "fatigue_horizon",
        "predicted_reps_to_failure": predicted_reps,
        "baseline_reps": fatigue_baseline_reps,
        "composite_penalty": round(composite, 4),
        "severity": severity,
        "constraint": constraint,
        "hmm_state": hmm_state,
        "component_penalties": {
            "iron_delivery": round(iron_penalty, 3),
            "rbc_capacity": round(rbc_penalty, 3),
            "hba1c_offloading": round(hba1c_penalty, 3),
            "spo2_realtime": round(spo2_penalty, 3),
            "cardiorespiratory": round(cardio_penalty, 3),
        },
        "iron_details": iron_details,
        "rbc_details": rbc_details,
        "hba1c_details": hba1c_details,
        "spo2_details": spo2_details,
        "cardio_details": cardio_details,
    }
    return result
