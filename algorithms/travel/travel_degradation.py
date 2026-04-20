"""
travel degradation index and dynamic homeostatic stabilization.
ref: pmc8279034 — managing travel fatigue consensus statement.
ref: pmc7137984 — medical issues with commercial flights.
ref: pmc10362518 — compression garments and venous return.
ref: pmc10520441 — long haul travel and sleep.
ref: pmc12624380 — simulated short-haul flights.
"""

from config.settings import (
    alpha_hypoxic,
    sea_level_pressure,
    cabin_pressure_default,
    beta_kinematic,
    venous_stasis_no_compression,
    venous_stasis_with_compression,
    gamma_circadian_east,
    gamma_circadian_west,
    dhs_venous_sitting_max_minutes,
    dhs_rmssd_deviation_threshold,
    dhs_spo2_critical,
)


def compute_hypoxic_tax(cabin_pressure_pa):
    """
    hypoxic stress from cabin altitude.
    ref: pmc7137984 — aerospace pressure effects.
    """
    pressure_ratio = 1.0 - (cabin_pressure_pa / sea_level_pressure)
    tax = alpha_hypoxic * pressure_ratio
    return max(0.0, tax)


def compute_kinematic_tax(flight_duration_hours, has_compression):
    """
    kinematic tax from prolonged immobility.
    ref: pmc10362518 — compression garments improve venous return.
    """
    if has_compression:
        stasis = venous_stasis_with_compression
    else:
        stasis = venous_stasis_no_compression

    tax = beta_kinematic * (flight_duration_hours * stasis)
    return max(0.0, tax)


def compute_circadian_tax(timezone_shift, direction):
    """
    circadian disruption tax based on direction and magnitude.
    ref: pmc8279034 — managing travel fatigue consensus statement.
    """
    if direction == "east":
        coeff = gamma_circadian_east
    else:
        coeff = gamma_circadian_west

    tax = coeff * timezone_shift * 0.01
    return max(0.0, tax)


def compute_tdi(cabin_pressure_pa, flight_duration_hours, timezone_shift,
                direction, has_compression):
    """
    travel degradation index (tdi) — predicted % drop in baseline readiness.
    tdi = hypoxic_tax + kinematic_tax + circadian_tax
    ref: project plan doc 2 — travel allostatic load model.
    """
    hypoxic = compute_hypoxic_tax(cabin_pressure_pa)
    kinematic = compute_kinematic_tax(flight_duration_hours, has_compression)
    circadian = compute_circadian_tax(timezone_shift, direction)

    tdi = hypoxic + kinematic + circadian
    tdi = min(1.0, tdi)

    result = {
        "tdi_percent": round(tdi * 100, 2),
        "hypoxic_tax": round(hypoxic, 4),
        "kinematic_tax": round(kinematic, 4),
        "circadian_tax": round(circadian, 4),
    }
    return tdi, result


def compute_dhs_trigger(current_value, baseline_mean, baseline_std):
    """
    dynamic homeostatic stabilization trigger.
    returns the z-score deviation from baseline.
    ref: pmc7137984 — medical issues with commercial flights.
    """
    if baseline_std == 0:
        return 0.0
    z_score = abs((current_value - baseline_mean) / baseline_std)
    return z_score


def generate_interventions(athlete):
    """
    generates intervention recommendations based on dhs thresholds.
    ref: pmc10362518 — compression garments.
    ref: pmc12624380 — short-haul flight performance effects.
    """
    interventions = []

    hrv_history = athlete.wearables["hrv_rmssd_30d"]
    hrv_mean = sum(hrv_history) / len(hrv_history)
    n = len(hrv_history)
    hrv_std = (sum((x - hrv_mean) ** 2 for x in hrv_history) / (n - 1)) ** 0.5
    current_hrv = hrv_history[-1]

    hrv_z = compute_dhs_trigger(current_hrv, hrv_mean, hrv_std)

    if hrv_z > dhs_rmssd_deviation_threshold:
        interventions.append({
            "trigger": "autonomic_deviation",
            "z_score": round(hrv_z, 2),
            "action": "paced resonance breathing at 5.5 breaths per minute",
            "priority": "high",
        })

    spo2_values = athlete.wearables.get("spo2_7d", [])
    if spo2_values:
        min_spo2 = min(spo2_values)
        if min_spo2 < dhs_spo2_critical:
            interventions.append({
                "trigger": "spo2_critical",
                "value": min_spo2,
                "action": "cabin mobility protocol and supplemental oxygen if available",
                "priority": "critical",
            })

    flight_duration = athlete.travel["flight"]["duration_hours"]
    sitting_blocks = int(flight_duration * 60 / dhs_venous_sitting_max_minutes)

    if sitting_blocks > 0:
        interventions.append({
            "trigger": "venous_stasis",
            "mobilization_intervals": sitting_blocks,
            "interval_minutes": dhs_venous_sitting_max_minutes,
            "action": "5 minute mobilization protocol with isometric calf contractions",
            "priority": "standard",
        })

    direction = athlete.direction()
    if direction == "east":
        interventions.append({
            "trigger": "circadian_advance_needed",
            "action": "blue light blocking glasses during flight, melatonin upon arrival evening",
            "priority": "standard",
        })
    else:
        interventions.append({
            "trigger": "circadian_delay_needed",
            "action": "bright light exposure during early flight hours, suppress melatonin",
            "priority": "standard",
        })

    return interventions


def compute_travel_degradation(athlete):
    """
    full travel degradation analysis.
    ref: project plan doc 2.
    """
    flight = athlete.travel["flight"]

    tdi_value, tdi_details = compute_tdi(
        cabin_pressure_pa=flight.get("cabin_pressure_pa", cabin_pressure_default),
        flight_duration_hours=flight["duration_hours"],
        timezone_shift=flight["timezone_shift"],
        direction=flight["direction"],
        has_compression=flight.get("has_compression_garments", False),
    )

    interventions = generate_interventions(athlete)

    predicted_readiness_drop = round(tdi_value * 100, 2)

    result = {
        "algorithm": "travel_degradation",
        "tdi": tdi_details,
        "predicted_readiness_drop_percent": predicted_readiness_drop,
        "interventions": interventions,
        "intervention_count": len(interventions),
    }
    return result
