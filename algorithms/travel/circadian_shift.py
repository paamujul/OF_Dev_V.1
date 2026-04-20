"""
multi-zeitgeber integration algorithm (mzia) for circadian re-engineering.
ref: khalsa et al. (2003), journal of physiology — photic prc.
ref: zeitzer et al. (2000), journal of physiology — light sensitivity.
ref: brainard et al. (2001), journal of neuroscience — melanopsin activation.
ref: burgess et al. (2010), journal of clinical sleep medicine — melatonin prc.
ref: youngstedt et al. (2019), journal of physiology — exercise prc.
ref: wehrens et al. (2017), current biology — meal timing.
"""

import math

from config.settings import (
    kappa_light,
    kappa_melatonin,
    kappa_exercise,
    kappa_feeding,
    light_half_max_lux,
    light_max_lux,
    dark_threshold_lux,
    blue_wavelength_peak,
    melatonin_default_dose_mg,
    idp_threshold_hours,
    max_phase_shift_per_day,
)


def compute_light_prc(phi, intensity_lux, wavelength_nm=None):
    """
    phase response to light based on biological time relative to tmin.
    ref: khalsa et al. (2003), journal of physiology.
    ref: zeitzer et al. (2000), journal of physiology.
    """
    if wavelength_nm is None:
        wavelength_nm = 550.0

    wavelength_efficiency = math.exp(
        -0.5 * ((wavelength_nm - blue_wavelength_peak) / 40.0) ** 2
    )

    intensity_response = intensity_lux / (intensity_lux + light_half_max_lux)

    if 1.0 <= phi <= 5.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi - 3.0) / 1.5) ** 2)
        shift_direction = 1.0
    elif -5.0 <= phi < -1.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi + 3.0) / 1.5) ** 2)
        shift_direction = -1.0
    else:
        temporal_sensitivity = 0.05
        shift_direction = 0.0

    shift = shift_direction * temporal_sensitivity * intensity_response * wavelength_efficiency
    return shift


def compute_melatonin_prc(phi, dose_mg):
    """
    phase response to exogenous melatonin — inverse prc to light.
    ref: burgess et al. (2010), journal of clinical sleep medicine.
    """
    dose_response = min(dose_mg / 0.5, 1.0)

    if -12.0 <= phi <= -8.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi + 10.0) / 1.5) ** 2)
        shift_direction = 1.0
    elif 6.0 <= phi <= 10.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi - 8.0) / 1.5) ** 2)
        shift_direction = -1.0
    else:
        temporal_sensitivity = 0.02
        shift_direction = 0.0

    shift = shift_direction * temporal_sensitivity * dose_response
    return shift


def compute_exercise_prc(phi, workload_watts):
    """
    phase response to high-intensity exercise.
    ref: youngstedt et al. (2019), journal of physiology.
    """
    workload_response = min(workload_watts / 300.0, 1.0)

    if 2.0 <= phi <= 5.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi - 3.0) / 1.5) ** 2)
        shift_direction = 1.0
    elif 8.0 <= phi <= 12.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi - 10.0) / 1.5) ** 2)
        shift_direction = 1.0
    else:
        temporal_sensitivity = 0.03
        shift_direction = 0.0

    shift = shift_direction * temporal_sensitivity * workload_response
    return shift


def compute_feeding_shift(meal_time_phi_target, meal_time_phi_current):
    """
    peripheral clock shift from meal timing.
    ref: wehrens et al. (2017), current biology.
    """
    delta = meal_time_phi_target - meal_time_phi_current
    peripheral_shift = delta * 0.2
    return peripheral_shift


def compute_daily_phase_shift(tmin_hour, light_schedule, melatonin_schedule,
                              exercise_schedule, feeding_schedule=None):
    """
    total daily phase shift from all zeitgebers.
    ref: project plan doc 4 — mzia equation.
    """
    total_shift = 0.0
    details = {
        "light_shift": 0.0,
        "melatonin_shift": 0.0,
        "exercise_shift": 0.0,
        "feeding_shift": 0.0,
    }

    for entry in light_schedule:
        hour = entry["hour"]
        phi = hour - tmin_hour
        intensity = entry.get("lux", 0)
        wavelength = entry.get("wavelength_nm", 550)
        shift = compute_light_prc(phi, intensity, wavelength)
        weighted = kappa_light * shift
        details["light_shift"] = details["light_shift"] + weighted
        total_shift = total_shift + weighted

    for entry in melatonin_schedule:
        hour = entry["hour"]
        phi = hour - tmin_hour
        dose = entry.get("dose_mg", melatonin_default_dose_mg)
        shift = compute_melatonin_prc(phi, dose)
        weighted = kappa_melatonin * shift
        details["melatonin_shift"] = details["melatonin_shift"] + weighted
        total_shift = total_shift + weighted

    for entry in exercise_schedule:
        hour = entry["hour"]
        phi = hour - tmin_hour
        watts = entry.get("watts", 200)
        shift = compute_exercise_prc(phi, watts)
        weighted = kappa_exercise * shift
        details["exercise_shift"] = details["exercise_shift"] + weighted
        total_shift = total_shift + weighted

    if feeding_schedule is not None:
        for entry in feeding_schedule:
            target_phi = entry.get("target_phi", 2.5)
            current_phi = entry.get("current_phi", 0.0)
            shift = compute_feeding_shift(target_phi, current_phi)
            weighted = kappa_feeding * shift
            details["feeding_shift"] = details["feeding_shift"] + weighted
            total_shift = total_shift + weighted

    total_shift = max(-max_phase_shift_per_day, min(max_phase_shift_per_day, total_shift))

    details["total_shift_hours"] = round(total_shift, 4)
    return total_shift, details


def compute_internal_desynchrony(scn_shift, peripheral_shift):
    """
    internal desynchrony penalty (idp).
    ref: project plan doc 4 — idp equation.
    """
    idp = abs(scn_shift - peripheral_shift)
    is_problematic = idp > idp_threshold_hours
    result = {
        "idp_hours": round(idp, 2),
        "threshold": idp_threshold_hours,
        "is_problematic": is_problematic,
    }
    if is_problematic:
        result["warning"] = (
            "gastrointestinal distress, compromised glycogen synthesis, "
            "and reduced peak neuromuscular force expected"
        )
    return result


def generate_zeitgeber_schedule(timezone_shift, direction, tmin_hour):
    """
    generates a multi-day zeitgeber protocol for circadian re-engineering.
    ref: project plan doc 4 — precision re-engineering protocol.
    """
    total_days = math.ceil(abs(timezone_shift) / max_phase_shift_per_day)
    schedule = []

    current_tmin = tmin_hour

    for day_num in range(1, total_days + 1):
        if direction == "east":
            light_entries = [
                {
                    "hour": round(current_tmin + 1.5, 1),
                    "lux": light_max_lux,
                    "wavelength_nm": blue_wavelength_peak,
                    "description": "blue-enriched bright light exposure",
                },
                {
                    "hour": round(current_tmin + 3.0, 1),
                    "lux": light_max_lux,
                    "wavelength_nm": blue_wavelength_peak,
                    "description": "sustained bright light exposure",
                },
            ]
            melatonin_entries = [
                {
                    "hour": round(current_tmin - 10.0 + 24.0, 1) % 24,
                    "dose_mg": melatonin_default_dose_mg,
                    "description": "exogenous melatonin for phase advance",
                },
            ]
            exercise_entries = [
                {
                    "hour": round(current_tmin + 10.0, 1),
                    "watts": 250,
                    "description": "high-intensity training for peripheral clock pull",
                },
            ]
            feeding_entries = [
                {
                    "target_phi": 2.5,
                    "current_phi": 0.0,
                    "description": "high-protein breakfast aligned to target zone",
                },
            ]
            dark_phase = {
                "start_hour": round((current_tmin - 4.0 + 24.0) % 24, 1),
                "end_hour": round(current_tmin + 1.0, 1),
                "max_lux": dark_threshold_lux,
                "note": "red-tinted blue-blocking glasses mandatory",
            }
        else:
            light_entries = [
                {
                    "hour": round(current_tmin - 3.0 + 24.0, 1) % 24,
                    "lux": light_max_lux,
                    "wavelength_nm": blue_wavelength_peak,
                    "description": "bright light exposure for phase delay",
                },
            ]
            melatonin_entries = [
                {
                    "hour": round(current_tmin + 8.0, 1),
                    "dose_mg": melatonin_default_dose_mg,
                    "description": "morning melatonin for phase delay",
                },
            ]
            exercise_entries = [
                {
                    "hour": round(current_tmin - 5.0 + 24.0, 1) % 24,
                    "watts": 250,
                    "description": "evening training for peripheral delay",
                },
            ]
            feeding_entries = [
                {
                    "target_phi": -2.5,
                    "current_phi": 0.0,
                    "description": "delayed meal timing for peripheral delay",
                },
            ]
            dark_phase = {
                "start_hour": round(current_tmin + 1.0, 1),
                "end_hour": round(current_tmin + 5.0, 1),
                "max_lux": dark_threshold_lux,
                "note": "strict early morning darkness",
            }

        daily_shift, shift_details = compute_daily_phase_shift(
            tmin_hour=current_tmin,
            light_schedule=light_entries,
            melatonin_schedule=melatonin_entries,
            exercise_schedule=exercise_entries,
            feeding_schedule=feeding_entries,
        )

        scn_shift = shift_details["light_shift"] + shift_details["melatonin_shift"]
        peripheral_shift = shift_details["exercise_shift"] + shift_details["feeding_shift"]
        idp_result = compute_internal_desynchrony(scn_shift, peripheral_shift)

        if direction == "east":
            current_tmin = current_tmin - abs(daily_shift)
        else:
            current_tmin = current_tmin + abs(daily_shift)

        day_protocol = {
            "day": day_num,
            "tmin_current": round(current_tmin, 2),
            "light_schedule": light_entries,
            "melatonin_schedule": melatonin_entries,
            "exercise_schedule": exercise_entries,
            "feeding_schedule": feeding_entries,
            "dark_phase": dark_phase,
            "shift_details": shift_details,
            "internal_desynchrony": idp_result,
        }
        schedule.append(day_protocol)

    result = {
        "algorithm": "circadian_shift",
        "direction": direction,
        "timezone_shift": timezone_shift,
        "total_adaptation_days": total_days,
        "daily_schedule": schedule,
        "estimated_full_adaptation_day": total_days,
    }
    return result
