"""
pinn for dynamic tissue tolerance (block mechanics).
predicts auto-regulatory velocity cap based on tissue damage and reflex inhibition.
ref: baumert et al. (2019), frontiers in physiology — ck and crp.
ref: ogan & pritchett (2013), sports health — vitamin d and fast-twitch.
ref: mah et al. (2011), sleep — sleep and connective tissue resilience.
ref: pons et al. (2021) — pinn for muscle biomechanics.
"""

from config.settings import (
    tissue_ck_weight,
    tissue_crp_weight,
    tissue_vitd_weight,
    tissue_sleep_weight,
    tissue_strain_weight,
    tissue_ck_safe,
    tissue_ck_danger,
    tissue_crp_safe,
    tissue_crp_danger,
    tissue_vitd_optimal,
    tissue_vitd_critical,
    tissue_strain_safe,
    tissue_strain_danger,
    tissue_baseline_vmax_ms,
    tissue_min_vmax_ms,
    tissue_athlete_mass_kg,
    tissue_spring_k_optimal,
    tissue_decel_distance_m,
)


def compute_ck_damage_penalty(ck_level):
    """
    ck as primary marker for eccentric muscle damage.
    ref: totsuka et al. (2002), journal of applied physiology.
    """
    if ck_level <= tissue_ck_safe:
        penalty = 0.0
    elif ck_level <= tissue_ck_danger:
        ck_range = tissue_ck_danger - tissue_ck_safe
        ck_excess = ck_level - tissue_ck_safe
        penalty = ck_excess / ck_range
    else:
        penalty = 1.0

    return penalty, {"creatine_kinase_u_l": ck_level}


def compute_crp_inflammation_penalty(hscrp_level):
    """
    hs-crp for systemic inflammation indicating secondary tissue damage.
    ref: baumert et al. (2019), frontiers in physiology.
    """
    if hscrp_level <= tissue_crp_safe:
        penalty = 0.0
    elif hscrp_level <= tissue_crp_danger:
        crp_range = tissue_crp_danger - tissue_crp_safe
        crp_excess = hscrp_level - tissue_crp_safe
        penalty = crp_excess / crp_range
    else:
        penalty = 1.0

    return penalty, {"hscrp_mg_l": hscrp_level}


def compute_vitd_penalty(vitd_level):
    """
    vitamin d and type ii fast-twitch fiber integrity.
    ref: ogan & pritchett (2013), sports health.
    """
    if vitd_level >= tissue_vitd_optimal:
        penalty = 0.0
    elif vitd_level >= tissue_vitd_critical:
        vd_range = tissue_vitd_optimal - tissue_vitd_critical
        vd_deficit = tissue_vitd_optimal - vitd_level
        penalty = vd_deficit / vd_range
    else:
        penalty = 1.0

    return penalty, {"vitamin_d_ng_ml": vitd_level}


def compute_tissue_sleep_penalty(sleep_efficiency):
    """
    sleep restriction degrades connective tissue resilience.
    ref: mah et al. (2011), sleep.
    """
    if sleep_efficiency >= 85.0:
        penalty = 0.0
    elif sleep_efficiency >= 70.0:
        se_range = 85.0 - 70.0
        se_deficit = 85.0 - sleep_efficiency
        penalty = se_deficit / se_range
    else:
        penalty = 1.0

    return penalty, {"sleep_efficiency": round(sleep_efficiency, 1)}


def compute_strain_penalty(strain_value):
    """
    accumulated systemic strain degrades high-frequency neural drive.
    """
    if strain_value <= tissue_strain_safe:
        penalty = 0.0
    elif strain_value <= tissue_strain_danger:
        s_range = tissue_strain_danger - tissue_strain_safe
        s_excess = strain_value - tissue_strain_safe
        penalty = s_excess / s_range
    else:
        penalty = 1.0

    return penalty, {"strain": strain_value}


def compute_spring_stiffness(composite_penalty):
    """
    physics-informed stiffness variable (k).
    constrained by impulse-momentum theorem and hooke's law.
    ref: pons et al. (2021) — pinn for muscle biomechanics.
    """
    k_effective = tissue_spring_k_optimal * (1.0 - composite_penalty * 0.6)
    k_effective = max(tissue_spring_k_optimal * 0.3, k_effective)

    max_force = k_effective * tissue_decel_distance_m

    return k_effective, max_force


def compute_velocity_cap(athlete):
    """
    master tissue tolerance function.
    outputs the auto-regulatory velocity cap for the session.
    """
    inflammatory = athlete.bloodwork.get("inflammatory_recovery", {})
    ck = inflammatory.get("creatine_kinase_u_l", tissue_ck_safe)
    ck_penalty, ck_details = compute_ck_damage_penalty(ck)

    hscrp = inflammatory.get("hscrp_mg_l", tissue_crp_safe)
    crp_penalty, crp_details = compute_crp_inflammation_penalty(hscrp)

    nutritional = athlete.bloodwork.get("nutritional_panel", {})
    vitd = nutritional.get("vitamin_d_ng_ml", tissue_vitd_optimal)
    vitd_penalty, vitd_details = compute_vitd_penalty(vitd)

    sleep_eff = athlete.avg_sleep_efficiency()
    sleep_penalty, sleep_details = compute_tissue_sleep_penalty(sleep_eff)

    strain_value = athlete.strain()
    strain_penalty, strain_details = compute_strain_penalty(strain_value)

    composite = (
        tissue_ck_weight * ck_penalty
        + tissue_crp_weight * crp_penalty
        + tissue_vitd_weight * vitd_penalty
        + tissue_sleep_weight * sleep_penalty
        + tissue_strain_weight * strain_penalty
    )

    k_effective, max_force = compute_spring_stiffness(composite)

    velocity_range = tissue_baseline_vmax_ms - tissue_min_vmax_ms
    velocity_cap = tissue_baseline_vmax_ms - (composite * velocity_range)
    velocity_cap = max(tissue_min_vmax_ms, velocity_cap)

    reflex_state = "intact"
    if composite > 0.7:
        reflex_state = "autonomic_reflex_breakdown"
    elif composite > 0.4:
        reflex_state = "protective_inhibition"
    elif composite > 0.2:
        reflex_state = "mild_guarding"

    if velocity_cap < 6.0:
        recommendation = (
            f"cap runway velocity at {round(velocity_cap, 1)} m/s — "
            "exceeding this will trigger protective inhibition and "
            "kinetic energy leakage at the block"
        )
    elif velocity_cap < 7.0:
        recommendation = (
            f"reduced approach velocity to {round(velocity_cap, 1)} m/s — "
            "tissue tolerance below optimal"
        )
    else:
        recommendation = "full velocity approach available"

    result = {
        "algorithm": "tissue_tolerance",
        "velocity_cap_ms": round(velocity_cap, 2),
        "baseline_vmax_ms": tissue_baseline_vmax_ms,
        "composite_penalty": round(composite, 4),
        "reflex_state": reflex_state,
        "recommendation": recommendation,
        "spring_stiffness": {
            "k_effective_n_m": round(k_effective, 1),
            "k_optimal_n_m": tissue_spring_k_optimal,
            "max_decel_force_n": round(max_force, 1),
        },
        "component_penalties": {
            "ck_damage": round(ck_penalty, 3),
            "crp_inflammation": round(crp_penalty, 3),
            "vitamin_d": round(vitd_penalty, 3),
            "sleep": round(sleep_penalty, 3),
            "strain": round(strain_penalty, 3),
        },
        "ck_details": ck_details,
        "crp_details": crp_details,
        "vitd_details": vitd_details,
        "sleep_details": sleep_details,
        "strain_details": strain_details,
    }
    return result
