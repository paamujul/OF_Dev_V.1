"""
telemetry-driven travel degradation index and dynamic homeostatic stabilization.
ref: muhm et al. (2007), nejm — spo2 in-flight telemetry.
ref: zalesin et al. (2001), annals of internal medicine — venous stasis.
ref: waterhouse et al. (2005), journal of sports sciences — skin temp proxy.
ref: botek et al. (2010), ejap — hrv and flight performance.
ref: juliff et al. (2015), jsms — sleep architecture and tz shifts.
"""

from config.settings import (
    alpha_spo2,
    beta_immobility,
    gamma_circadian_east,
    gamma_circadian_west,
    dhs_venous_sitting_max_minutes,
    dhs_rmssd_deviation_threshold,
    dhs_spo2_critical,
    dhs_circadian_advance_per_day,
)


def compute_hypoxic_tax(spo2_baseline, spo2_transit):
    """
    hypoxic stress from direct spo2 telemetry delta.
    ref: muhm et al. (2007), nejm.
    """
    delta_spo2 = max(0.0, spo2_baseline - spo2_transit)
    tax = alpha_spo2 * delta_spo2 * 0.01
    return max(0.0, tax)


def compute_kinematic_tax(flight_duration_hours, active_minutes_inflight):
    """
    kinematic tax from tracked immobility.
    ref: zalesin et al. (2001), annals of internal medicine.
    """
    flight_minutes = flight_duration_hours * 60.0
    immobile_minutes = max(0.0, flight_minutes - active_minutes_inflight)
    tax = beta_immobility * immobile_minutes * 0.001
    return max(0.0, tax)


def compute_circadian_tax(timezone_shift, direction):
    """
    circadian disruption tax based on direction and magnitude.
    ref: juliff et al. (2015), jsms.
    """
    if direction == "east":
        coeff = gamma_circadian_east
    else:
        coeff = gamma_circadian_west

    tax = coeff * timezone_shift * 0.01
    return max(0.0, tax)


def compute_tdi(spo2_baseline, spo2_transit, flight_duration_hours,
                active_minutes_inflight, timezone_shift, direction):
    """
    wearable travel degradation index (tdi_wearable).
    tdi = hypoxic_tax + kinematic_tax + circadian_tax
    ref: project plan doc 2 — telemetry-driven travel degradation.
    """
    hypoxic = compute_hypoxic_tax(spo2_baseline, spo2_transit)
    kinematic = compute_kinematic_tax(flight_duration_hours, active_minutes_inflight)
    circadian = compute_circadian_tax(timezone_shift, direction)

    tdi = hypoxic + kinematic + circadian
    tdi = min(1.0, tdi)

    result = {
        "tdi_percent": round(tdi * 100, 2),
        "hypoxic_tax": round(hypoxic, 4),
        "kinematic_tax": round(kinematic, 4),
        "circadian_tax": round(circadian, 4),
        "spo2_delta": round(max(0.0, spo2_baseline - spo2_transit), 1),
        "immobile_minutes": round(
            max(0.0, flight_duration_hours * 60 - active_minutes_inflight), 1
        ),
    }
    return tdi, result


def compute_dhs_trigger(current_value, baseline_mean, baseline_std):
    """
    dynamic homeostatic stabilization trigger.
    returns the z-score deviation from baseline.
    ref: botek et al. (2010), ejap.
    """
    if baseline_std == 0:
        return 0.0
    z_score = abs((current_value - baseline_mean) / baseline_std)
    return z_score


def generate_interventions(athlete):
    """
    generates wearable-driven intervention recommendations.
    ref: muhm et al. (2007), zalesin et al. (2001), waterhouse et al. (2005).
    """
    interventions = []

    hrv_history = athlete.wearables["hrv_rmssd_30d"]
    hrv_mean = sum(hrv_history) / len(hrv_history)
    n = len(hrv_history)
    hrv_std = (sum((x - hrv_mean) ** 2 for x in hrv_history) / (n - 1)) ** 0.5
    current_hrv = hrv_history[-1]

    hrv_z = compute_dhs_trigger(current_hrv, hrv_mean, hrv_std)

    spo2_transit = athlete.spo2_transit()

    if spo2_transit < dhs_spo2_critical or hrv_z > dhs_rmssd_deviation_threshold:
        interventions.append({
            "trigger": "hypoxic_autonomic",
            "hrv_z_score": round(hrv_z, 2),
            "spo2_transit": spo2_transit,
            "action": "mandatory tactical breathing protocol to raise spo2 and stabilize ans",
            "priority": "critical" if spo2_transit < dhs_spo2_critical else "high",
        })

    flight_duration = athlete.travel["flight"]["duration_hours"]
    active_minutes = athlete.active_minutes_inflight()
    sitting_minutes = flight_duration * 60 - active_minutes
    stasis_blocks = int(sitting_minutes / dhs_venous_sitting_max_minutes)

    if stasis_blocks > 0:
        interventions.append({
            "trigger": "venous_stasis",
            "mobilization_intervals": stasis_blocks,
            "interval_minutes": dhs_venous_sitting_max_minutes,
            "action": "5 minute mobilization protocol with isometric calf contractions",
            "priority": "standard",
        })

    direction = athlete.direction()
    skin_temps = athlete.nighttime_skin_temps()
    if skin_temps:
        interventions.append({
            "trigger": "circadian_sync",
            "direction": direction,
            "expected_advance_per_day": dhs_circadian_advance_per_day,
            "action": (
                "time high-intensity exercise at wtmin + 10 hours "
                "to drag peripheral clocks into alignment"
                if direction == "east"
                else "bright light exposure during early activity hours, "
                     "delay exercise to late afternoon"
            ),
            "priority": "standard",
        })

    return interventions


def compute_travel_degradation(athlete):
    """
    full wearable-driven travel degradation analysis.
    ref: project plan doc 2 — telemetry-driven tdi.
    """
    flight = athlete.travel["flight"]

    tdi_value, tdi_details = compute_tdi(
        spo2_baseline=athlete.spo2_baseline(),
        spo2_transit=athlete.spo2_transit(),
        flight_duration_hours=flight["duration_hours"],
        active_minutes_inflight=athlete.active_minutes_inflight(),
        timezone_shift=flight["timezone_shift"],
        direction=flight["direction"],
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
