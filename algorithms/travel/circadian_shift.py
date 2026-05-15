"""
wearable-driven multi-zeitgeber integration algorithm (wmzia).
ref: papini et al. (2020), ieee trans biomed eng — wearable circadian estimation.
ref: wright et al. (2013), current biology — gps light-dark entrainment.
ref: youngstedt et al. (2019), journal of physiology — exercise prc.
ref: dijk & czeisler (1995), journal of neuroscience — sleep architecture.
ref: boudreau et al. (2013), sleep — hrv circadian variation.
"""

import math
import statistics

from config.settings import (
    kappa_light,
    kappa_exercise,
    light_half_max_lux,
    light_max_lux,
    dark_threshold_lux,
    blue_wavelength_peak,
    exercise_prc_min_duration_minutes,
    exercise_prc_min_strain,
    exercise_prc_min_zone45_minutes,
    idp_threshold_hours,
    rem_drop_threshold_percent,
    sleep_efficiency_desync_threshold,
    max_phase_shift_per_day,
)


def compute_wtmin(nighttime_skin_temps, nighttime_rhrs, fallback_tmin=5.0):
    """
    wearable tmin locator — finds the biological clock nadir.
    scans nighttime data for peak skin temp coinciding with lowest rhr.
    ref: papini et al. (2020), ieee trans biomed eng.
    """
    if isinstance(nighttime_skin_temps, (float, int)):
        nighttime_skin_temps = [nighttime_skin_temps]
    if isinstance(nighttime_rhrs, (float, int)):
        nighttime_rhrs = [nighttime_rhrs]

    if not nighttime_skin_temps or not nighttime_rhrs:
        return fallback_tmin

    length = min(len(nighttime_skin_temps), len(nighttime_rhrs))
    skin_temps = nighttime_skin_temps[:length]
    rhrs = nighttime_rhrs[:length]

    max_skin = max(skin_temps)
    min_rhr = min(rhrs)

    skin_peak_idx = skin_temps.index(max_skin)
    rhr_trough_idx = rhrs.index(min_rhr)

    avg_idx = (skin_peak_idx + rhr_trough_idx) / 2.0

    sleep_start_hour = 23.0
    hours_per_index = 7.0 / max(length - 1, 1)
    wtmin = (sleep_start_hour + avg_idx * hours_per_index) % 24.0

    return round(wtmin, 2)


def compute_light_prc(phi, intensity_lux, wavelength_nm=None):
    """
    phase response to light based on gps-derived sun position and sleep/wake.
    ref: wright et al. (2013), current biology.
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


def compute_exercise_prc(phi, strain, duration_minutes, zone45_minutes):
    """
    wearable-driven exercise phase response.
    only awards shift if duration > 45 min, strain > 14, zone 4-5 > 20 min.
    ref: youngstedt et al. (2019), journal of physiology.
    """
    qualifies = (
        duration_minutes >= exercise_prc_min_duration_minutes
        and strain >= exercise_prc_min_strain
        and zone45_minutes >= exercise_prc_min_zone45_minutes
    )

    if not qualifies:
        return 0.0

    strain_response = min(strain / 20.0, 1.0)

    if 2.0 <= phi <= 5.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi - 3.0) / 1.5) ** 2)
        shift_direction = 1.0
    elif 8.0 <= phi <= 12.0:
        temporal_sensitivity = math.exp(-0.5 * ((phi - 10.0) / 1.5) ** 2)
        shift_direction = 1.0
    else:
        temporal_sensitivity = 0.03
        shift_direction = 0.0

    shift = shift_direction * temporal_sensitivity * strain_response
    return shift


def compute_daily_phase_shift(wtmin_hour, light_schedule, exercise_schedule):
    """
    total daily phase shift from wearable-tracked zeitgebers.
    uses only light (gps/sleep) and exercise (hr zones/strain).
    ref: project plan doc 4 — wmzia equation.
    """
    total_shift = 0.0
    details = {
        "light_shift": 0.0,
        "exercise_shift": 0.0,
    }

    for entry in light_schedule:
        hour = entry["hour"]
        phi = hour - wtmin_hour
        intensity = entry.get("lux", 0)
        wavelength = entry.get("wavelength_nm", 550)
        shift = compute_light_prc(phi, intensity, wavelength)
        weighted = kappa_light * shift
        details["light_shift"] = details["light_shift"] + weighted
        total_shift = total_shift + weighted

    for entry in exercise_schedule:
        hour = entry["hour"]
        phi = hour - wtmin_hour
        strain = entry.get("strain", 0)
        duration = entry.get("duration_minutes", 0)
        zone45 = entry.get("zone45_minutes", 0)
        shift = compute_exercise_prc(phi, strain, duration, zone45)
        weighted = kappa_exercise * shift
        details["exercise_shift"] = details["exercise_shift"] + weighted
        total_shift = total_shift + weighted

    total_shift = max(-max_phase_shift_per_day, min(max_phase_shift_per_day, total_shift))

    details["total_shift_hours"] = round(total_shift, 4)
    return total_shift, details


def compute_sleep_fragmentation_penalty(current_rem_percent, baseline_rem_percent,
                                        sleep_efficiency):
    """
    sleep architecture penalty (psi) for internal desynchrony.
    ref: dijk & czeisler (1995), journal of neuroscience.
    """
    psi = 0.0

    if baseline_rem_percent > 0:
        rem_drop = ((baseline_rem_percent - current_rem_percent) / baseline_rem_percent) * 100.0
        if rem_drop > rem_drop_threshold_percent:
            psi = psi + (rem_drop - rem_drop_threshold_percent) * 0.02

    if sleep_efficiency < sleep_efficiency_desync_threshold:
        efficiency_penalty = (sleep_efficiency_desync_threshold - sleep_efficiency) * 0.05
        psi = psi + efficiency_penalty

    return round(psi, 4)


def compute_internal_desynchrony(scn_shift, peripheral_shift,
                                 current_rem_percent, baseline_rem_percent,
                                 sleep_efficiency):
    """
    wearable internal desynchrony penalty (widp).
    includes sleep fragmentation penalty (psi).
    ref: project plan doc 4 — widp equation.
    """
    base_idp = abs(scn_shift - peripheral_shift)

    psi = compute_sleep_fragmentation_penalty(
        current_rem_percent, baseline_rem_percent, sleep_efficiency
    )

    widp = base_idp + psi
    is_problematic = widp > idp_threshold_hours

    result = {
        "widp_hours": round(widp, 2),
        "base_idp": round(base_idp, 2),
        "psi_fragmentation": psi,
        "threshold": idp_threshold_hours,
        "is_problematic": is_problematic,
    }
    if is_problematic:
        result["warning"] = (
            "severe internal desynchrony detected — "
            "mandate high-strain exercise at wtmin + 10 hours "
            "to forcefully align peripheral clocks"
        )
    return result


def generate_zeitgeber_schedule(timezone_shift, direction, athlete):
    """
    generates a wearable-driven multi-day zeitgeber protocol.
    uses wtmin from nighttime skin temp / rhr instead of static bio value.
    ref: project plan doc 4 — wearable precision re-engineering protocol.
    """
    wtmin = compute_wtmin(
        athlete.nighttime_skin_temps(),
        athlete.nighttime_rhrs(),
        fallback_tmin=athlete.bio.get("tmin_hour", 5.0),
    )

    total_days = math.ceil(abs(timezone_shift) / max_phase_shift_per_day)
    schedule = []

    current_wtmin = wtmin

    strain = athlete.strain()
    hr_zones = athlete.hr_zone_minutes()
    session_minutes = athlete.wearables.get("session_duration_minutes", 75)
    zone45 = hr_zones.get("zone4", 0) + hr_zones.get("zone5", 0)

    current_rem = athlete.avg_rem_percent()
    baseline_rem = athlete.baseline_rem_percent()
    sleep_eff = athlete.avg_sleep_efficiency()

    for day_num in range(1, total_days + 1):
        if direction == "east":
            light_entries = [
                {
                    "hour": round(current_wtmin + 1.5, 1),
                    "lux": light_max_lux,
                    "wavelength_nm": blue_wavelength_peak,
                    "description": "blue-enriched bright light post-wtmin",
                },
                {
                    "hour": round(current_wtmin + 3.0, 1),
                    "lux": light_max_lux,
                    "wavelength_nm": blue_wavelength_peak,
                    "description": "sustained bright light for phase advance",
                },
            ]
            exercise_entries = [
                {
                    "hour": round(current_wtmin + 10.0, 1),
                    "strain": strain,
                    "duration_minutes": session_minutes,
                    "zone45_minutes": zone45,
                    "description": "high-intensity training for peripheral clock advance",
                },
            ]
            dark_phase = {
                "start_hour": round((current_wtmin - 4.0 + 24.0) % 24, 1),
                "end_hour": round(current_wtmin + 1.0, 1),
                "max_lux": dark_threshold_lux,
                "note": "red-tinted blue-blocking glasses mandatory",
            }
        else:
            light_entries = [
                {
                    "hour": round((current_wtmin - 3.0 + 24.0) % 24, 1),
                    "lux": light_max_lux,
                    "wavelength_nm": blue_wavelength_peak,
                    "description": "bright light exposure for phase delay",
                },
            ]
            exercise_entries = [
                {
                    "hour": round((current_wtmin - 5.0 + 24.0) % 24, 1),
                    "strain": strain,
                    "duration_minutes": session_minutes,
                    "zone45_minutes": zone45,
                    "description": "evening training for peripheral delay",
                },
            ]
            dark_phase = {
                "start_hour": round(current_wtmin + 1.0, 1),
                "end_hour": round(current_wtmin + 5.0, 1),
                "max_lux": dark_threshold_lux,
                "note": "strict early morning darkness",
            }

        daily_shift, shift_details = compute_daily_phase_shift(
            wtmin_hour=current_wtmin,
            light_schedule=light_entries,
            exercise_schedule=exercise_entries,
        )

        scn_shift = shift_details["light_shift"]
        peripheral_shift = shift_details["exercise_shift"]
        widp_result = compute_internal_desynchrony(
            scn_shift, peripheral_shift,
            current_rem, baseline_rem, sleep_eff,
        )

        if direction == "east":
            current_wtmin = current_wtmin - abs(daily_shift)
        else:
            current_wtmin = current_wtmin + abs(daily_shift)

        day_protocol = {
            "day": day_num,
            "wtmin_current": round(current_wtmin, 2),
            "light_schedule": light_entries,
            "exercise_schedule": exercise_entries,
            "dark_phase": dark_phase,
            "shift_details": shift_details,
            "internal_desynchrony": widp_result,
        }
        schedule.append(day_protocol)

    result = {
        "algorithm": "circadian_shift",
        "direction": direction,
        "timezone_shift": timezone_shift,
        "wtmin_computed": wtmin,
        "total_adaptation_days": total_days,
        "daily_schedule": schedule,
        "estimated_full_adaptation_day": total_days,
    }
    return result
