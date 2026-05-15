"""
wearable-adapted thermoregulatory performance model (watpm).
ref: buller et al. (2013), physiological measurement — core temp estimation.
ref: gagnon et al. (2013), journal of applied physiology — energy and sweat.
ref: liljegren et al. (2008), joeh — ewbgt approximation.
ref: welles et al. (2017), msse — skin temp as thermoregulatory proxy.
ref: duking et al. (2016), frontiers in physiology, pmc4754445.
"""

import math

from config.settings import (
    w_thermal,
    w_fluid,
    w_metabolic,
    core_temp_baseline,
    core_temp_ceiling,
    core_temp_alpha,
    ewbgt_precool_threshold,
    k_dehydration,
    fluid_energy_trigger_kcal,
    fluid_hr_zone_trigger_minutes,
    acclimation_half_days,
    acclimation_full_days,
    clothing_factor_default,
)


def estimate_ewbgt(temp_c, humidity_percent, wind_speed_m_s, solar_radiation_w_m2):
    """
    estimated wet bulb globe temperature from api weather data.
    ref: liljegren et al. (2008), joeh.
    """
    e_sat = 6.105 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    vapor_pressure = e_sat * (humidity_percent / 100.0)

    tw_approx = (
        temp_c * math.atan(0.151977 * (humidity_percent + 8.313659) ** 0.5)
        + math.atan(temp_c + humidity_percent)
        - math.atan(humidity_percent - 1.676331)
        + 0.00391838 * humidity_percent ** 1.5 * math.atan(0.023101 * humidity_percent)
        - 4.686035
    )

    tg_approx = temp_c + (1.5 * solar_radiation_w_m2 / 1000.0)

    ewbgt = 0.7 * tw_approx + 0.2 * tg_approx + 0.1 * temp_c
    return round(ewbgt, 2)


def compute_thermal_load(energy_burned_rate, solar_radiation_w_m2, clothing_factor,
                         wind_speed_m_s, skin_temp_c, temp_c, humidity_percent):
    """
    estimated thermal load vector (e_phi_thermal).
    uses wearable energy burned rate as metabolic heat proxy.
    ref: buller et al. (2013), physiological measurement.
    """
    e_required = energy_burned_rate + (solar_radiation_w_m2 * clothing_factor)

    e_sat_skin = 6.105 * math.exp((17.27 * skin_temp_c) / (237.7 + skin_temp_c))
    e_sat_ambient = 6.105 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    vapor_pressure_ambient = e_sat_ambient * (humidity_percent / 100.0)

    pressure_gradient = e_sat_skin - vapor_pressure_ambient

    wind_factor = max(wind_speed_m_s, 0.1) ** 0.6
    e_max = wind_factor * pressure_gradient

    if e_max <= 0:
        return 1.0

    phi_thermal = e_required / e_max
    phi_thermal = max(0.0, min(1.0, phi_thermal))
    return phi_thermal


def compute_fluid_vector(energy_burned, strain, ewbgt):
    """
    wearable-driven fluid loss vector (e_phi_fluid).
    uses energy burned * strain * ewbgt to model cardiovascular fluid penalty.
    ref: gagnon et al. (2013), journal of applied physiology.
    """
    exponent = k_dehydration * energy_burned * strain * ewbgt
    phi_fluid = math.exp(exponent) - 1.0
    phi_fluid = max(0.0, min(1.0, phi_fluid))

    alert_status = "normal"
    if exponent > 0.05:
        alert_status = "critical"
    elif exponent > 0.02:
        alert_status = "warning"

    details = {
        "energy_burned": round(energy_burned, 1),
        "strain": round(strain, 1),
        "ewbgt_factor": round(ewbgt, 2),
        "exponent": round(exponent, 6),
        "alert_status": alert_status,
    }
    return phi_fluid, details


def estimate_core_temp(skin_temp_c, hr_active, hr_rest):
    """
    estimated core temperature using extended kalman filter approach.
    ref: buller et al. (2013), physiological measurement.
    """
    hr_delta = max(0, hr_active - hr_rest)
    e_tcore = skin_temp_c + core_temp_alpha * hr_delta
    return round(e_tcore, 2)


def compute_metabolic_shift(skin_temp_c, hr_active, hr_rest):
    """
    wearable metabolic shift vector (e_phi_metabolic).
    ref: welles et al. (2017), msse.
    """
    e_tcore = estimate_core_temp(skin_temp_c, hr_active, hr_rest)

    denominator = core_temp_ceiling - core_temp_baseline
    if denominator <= 0:
        return 0.0, e_tcore

    phi_metabolic = (e_tcore - core_temp_baseline) / denominator
    phi_metabolic = max(0.0, min(1.0, phi_metabolic))

    return phi_metabolic, e_tcore


def compute_acclimation_factor(days_at_destination):
    """
    heat acclimation factor (gamma).
    exponential approach to full acclimation over ~14 days.
    """
    if days_at_destination <= 0:
        return 1.0

    decay = math.log(2) / acclimation_half_days
    gamma = 1.0 - (1.0 - math.exp(-decay * days_at_destination)) * 0.3
    gamma = max(0.7, min(1.0, gamma))
    return round(gamma, 4)


def compute_expected_power(athlete):
    """
    expected power output as percentage of baseline — watpm model.
    p_exp = 100 - [(w1 * phi_thermal + w2 * phi_fluid + w3 * phi_metabolic) * gamma * 100]
    ref: project plan doc 3 — wearable-adapted thermoregulatory performance model.
    """
    dest = athlete.travel["destination"]
    bio = athlete.bio
    wearables = athlete.wearables

    ewbgt = estimate_ewbgt(
        temp_c=dest["temp_c"],
        humidity_percent=dest["humidity_percent"],
        wind_speed_m_s=dest.get("wind_speed_m_s", 2.0),
        solar_radiation_w_m2=dest.get("solar_radiation_w_m2", 500),
    )

    hr_active = wearables["active_hr_bpm_last_session"]
    hr_rest = athlete.resting_hr_mean()
    skin_temp = athlete.avg_skin_temp()
    clothing = clothing_factor_default

    energy_burned = wearables["active_energy_kcal_last_session"]
    session_minutes = wearables.get("session_duration_minutes", 90)
    energy_rate = energy_burned / max(session_minutes, 1) * 60.0

    phi_thermal = compute_thermal_load(
        energy_burned_rate=energy_rate,
        solar_radiation_w_m2=dest.get("solar_radiation_w_m2", 500),
        clothing_factor=clothing,
        wind_speed_m_s=dest.get("wind_speed_m_s", 2.0),
        skin_temp_c=skin_temp,
        temp_c=dest["temp_c"],
        humidity_percent=dest["humidity_percent"],
    )

    strain = athlete.strain()
    phi_fluid, fluid_details = compute_fluid_vector(energy_burned, strain, ewbgt)

    phi_metabolic, e_tcore = compute_metabolic_shift(skin_temp, hr_active, hr_rest)

    days = athlete.travel["event"].get("arrival_days_before_event", 0)
    gamma = compute_acclimation_factor(days)

    weighted_strain = (
        w_thermal * phi_thermal
        + w_fluid * phi_fluid
        + w_metabolic * phi_metabolic
    )

    p_exp = 100.0 - (weighted_strain * gamma * 100.0)
    p_exp = max(0.0, min(100.0, p_exp))

    precool_needed = ewbgt > ewbgt_precool_threshold

    hr_zones = athlete.hr_zone_minutes()
    zone3_plus = (
        hr_zones.get("zone3", 0)
        + hr_zones.get("zone4", 0)
        + hr_zones.get("zone5", 0)
    )

    triggers = []
    if precool_needed:
        triggers.append({
            "type": "precooling",
            "ewbgt": ewbgt,
            "action": "ice slurry ingestion 45 minutes before start",
        })
    if e_tcore > 38.8:
        triggers.append({
            "type": "pacing_reduction",
            "estimated_core_temp": e_tcore,
            "action": "reduce power output by 5 to 10 percent",
        })
    if (energy_burned > fluid_energy_trigger_kcal
            and zone3_plus > fluid_hr_zone_trigger_minutes):
        triggers.append({
            "type": "rehydration",
            "energy_burned": energy_burned,
            "zone3_plus_minutes": zone3_plus,
            "action": "haptic alert for electrolyte fluid consumption",
        })

    result = {
        "algorithm": "thermoregulatory",
        "expected_power_percent": round(p_exp, 2),
        "ewbgt": ewbgt,
        "phi_thermal": round(phi_thermal, 4),
        "phi_fluid": round(phi_fluid, 4),
        "phi_metabolic": round(phi_metabolic, 4),
        "estimated_core_temp": e_tcore,
        "acclimation_factor": gamma,
        "fluid_details": fluid_details,
        "triggers": triggers,
        "precool_needed": precool_needed,
    }
    return result
