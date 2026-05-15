"""
endocrine-architecture power profiler (metabolic & hormonal readiness).
predicts daily rate of force development (rfd) ceiling from endocrine state.
ref: crewther et al. (2011), sports medicine — steroid hormones and power.
ref: leproult & van cauter (2011), jama — sleep restriction and testosterone.
ref: urhausen et al. (1995), sports medicine — ft:c ratio and overtraining.
ref: kraemer & ratamess (2005), sports medicine — hormones and resistance.
ref: biolo et al. (1999), american journal of physiology — insulin and recovery.
"""

from config.settings import (
    power_ftc_weight,
    power_insulin_weight,
    power_hr_zone_weight,
    power_sleep_weight,
    power_ftc_catabolic_drop_percent,
    power_insulin_low_threshold,
    power_insulin_optimal,
    power_hr_zone45_overload_minutes,
    power_sleep_efficiency_floor,
    power_baseline_rfd_percent,
    power_max_rfd_drop_percent,
)


def compute_ftc_power_penalty(ft_ratio, ft_baseline):
    """
    ft:c ratio penalty for anabolic-catabolic balance.
    ref: urhausen et al. (1995), sports medicine.
    """
    if ft_baseline <= 0:
        return 0.0, {"ftc_status": "insufficient_data"}

    deficit_fraction = (ft_baseline - ft_ratio) / ft_baseline
    deficit_fraction = max(0.0, deficit_fraction)

    catabolic_threshold = power_ftc_catabolic_drop_percent / 100.0

    if deficit_fraction > catabolic_threshold:
        penalty = 1.0
        status = "catabolic"
    elif deficit_fraction > catabolic_threshold * 0.5:
        penalty = deficit_fraction / catabolic_threshold
        status = "stressed"
    else:
        penalty = deficit_fraction / catabolic_threshold * 0.5
        status = "normal"

    details = {
        "ftc_deficit_percent": round(deficit_fraction * 100, 2),
        "ftc_status": status,
        "ft_ratio_current": ft_ratio,
        "ft_ratio_baseline": ft_baseline,
    }
    return penalty, details


def compute_insulin_power_penalty(fasting_insulin):
    """
    basal insulin as proxy for glycogen replenishment capacity.
    ref: biolo et al. (1999), american journal of physiology.
    """
    if fasting_insulin >= power_insulin_optimal:
        penalty = 0.0
    elif fasting_insulin >= power_insulin_low_threshold:
        insulin_range = power_insulin_optimal - power_insulin_low_threshold
        insulin_deficit = power_insulin_optimal - fasting_insulin
        penalty = insulin_deficit / insulin_range
    else:
        penalty = 1.0

    return penalty, {"fasting_insulin_uiu_ml": fasting_insulin}


def compute_hr_zone_penalty(zone45_minutes):
    """
    cumulative red-zone hr without recovery drives hpa axis overdrive.
    ref: crewther et al. (2011), sports medicine.
    """
    if zone45_minutes <= power_hr_zone45_overload_minutes * 0.5:
        penalty = 0.0
    elif zone45_minutes <= power_hr_zone45_overload_minutes:
        load_range = power_hr_zone45_overload_minutes * 0.5
        load_excess = zone45_minutes - power_hr_zone45_overload_minutes * 0.5
        penalty = load_excess / load_range
    else:
        penalty = 1.0

    return penalty, {"zone45_minutes": zone45_minutes}


def compute_sleep_power_penalty(sleep_efficiency):
    """
    poor sleep architecture suppresses free testosterone.
    ref: leproult & van cauter (2011), jama.
    """
    if sleep_efficiency >= 85.0:
        penalty = 0.0
    elif sleep_efficiency >= power_sleep_efficiency_floor:
        se_range = 85.0 - power_sleep_efficiency_floor
        se_deficit = 85.0 - sleep_efficiency
        penalty = se_deficit / se_range
    else:
        penalty = 1.0

    return penalty, {"sleep_efficiency": round(sleep_efficiency, 1)}


def compute_explosive_ceiling(athlete):
    """
    master power profiler.
    predicts the daily rfd capacity as a percentage of baseline.
    """
    hormonal = athlete.bloodwork.get("hormonal_panel", {})
    ft_ratio = hormonal.get("ft_cortisol_ratio", 1.0)
    ft_baseline = hormonal.get("ft_cortisol_ratio_baseline", 1.0)
    ftc_penalty, ftc_details = compute_ftc_power_penalty(ft_ratio, ft_baseline)

    metabolic = athlete.bloodwork.get("metabolic_panel", {})
    fasting_insulin = metabolic.get("fasting_insulin_uiu_ml", power_insulin_optimal)
    insulin_penalty, insulin_details = compute_insulin_power_penalty(fasting_insulin)

    zone45 = athlete.hr_zone45_minutes()
    hr_penalty, hr_details = compute_hr_zone_penalty(zone45)

    sleep_eff = athlete.avg_sleep_efficiency()
    sleep_penalty, sleep_details = compute_sleep_power_penalty(sleep_eff)

    composite_penalty = (
        power_ftc_weight * ftc_penalty
        + power_insulin_weight * insulin_penalty
        + power_hr_zone_weight * hr_penalty
        + power_sleep_weight * sleep_penalty
    )

    rfd_drop = composite_penalty * power_max_rfd_drop_percent
    rfd_ceiling = power_baseline_rfd_percent - rfd_drop
    rfd_ceiling = max(
        power_baseline_rfd_percent - power_max_rfd_drop_percent, rfd_ceiling
    )

    if rfd_ceiling < 70:
        status = "catabolic_suppression"
        recommendation = (
            "cap high-intensity throws — "
            f"rfd capacity at {round(rfd_ceiling, 1)}% of baseline. "
            "prioritize cns recovery and avoid explosive loading"
        )
    elif rfd_ceiling < 85:
        status = "reduced_drive"
        recommendation = (
            f"rfd operating at {round(rfd_ceiling, 1)}% — "
            "limit full-effort throws to 60% volume"
        )
    elif rfd_ceiling < 95:
        status = "mildly_suppressed"
        recommendation = "minor endocrine suppression — monitor training load"
    else:
        status = "optimal"
        recommendation = "full explosive capacity available"

    result = {
        "algorithm": "power_profiler",
        "rfd_ceiling_percent": round(rfd_ceiling, 2),
        "rfd_drop_percent": round(rfd_drop, 2),
        "status": status,
        "recommendation": recommendation,
        "component_penalties": {
            "ftc_ratio": round(ftc_penalty, 3),
            "insulin": round(insulin_penalty, 3),
            "hr_zones": round(hr_penalty, 3),
            "sleep": round(sleep_penalty, 3),
        },
        "ftc_details": ftc_details,
        "insulin_details": insulin_details,
        "hr_zone_details": hr_details,
        "sleep_details": sleep_details,
    }
    return result
