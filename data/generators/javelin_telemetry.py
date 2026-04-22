"""
12-week mock telemetry generator for an elite male javelin thrower
"""

import os
import sys
import json
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config.settings import (
    max_squat_kg,
    max_hang_clean_kg,
    max_pullover_kg,
    max_release_velocity_ms,
    target_release_angle_deg,
    target_attack_angle_deg,
    target_runup_velocity_ms,
    baseline_energy_transfer_wkg,
    plyo_contacts_base,
    plyo_contacts_strength,
    plyo_contacts_taper,
    intensity_mod_hypertrophy,
    intensity_mod_strength,
    intensity_mod_peaking,
    velocity_mod_hypertrophy,
    velocity_mod_strength,
    velocity_mod_peaking,
)


def resolve_phase(week):
    """returns periodization phase parameters for a given training week."""
    if week <= 4:
        return {
            "name": "base_hypertrophy",
            "intensity": intensity_mod_hypertrophy,
            "velocity": velocity_mod_hypertrophy,
            "plyo_mean": plyo_contacts_base,
            "plyo_std": 10,
        }
    elif week <= 8:
        return {
            "name": "maximal_strength",
            "intensity": intensity_mod_strength,
            "velocity": velocity_mod_strength,
            "plyo_mean": plyo_contacts_strength,
            "plyo_std": 8,
        }
    return {
        "name": "peaking_taper",
        "intensity": intensity_mod_peaking,
        "velocity": velocity_mod_peaking,
        "plyo_mean": plyo_contacts_taper,
        "plyo_std": 5,
    }


def resolve_session(weekday):
    """maps weekday index to session type."""
    if weekday in [0, 2, 4]:
        return "gym_cns_plyometrics"
    elif weekday in [1, 3, 5]:
        return "runway_technical"
    return "recovery"


def build_gym_record(phase, rng):
    """generates gym session metrics scaled by periodization phase."""
    daily_variance = rng.normal(1.0, 0.02)
    plyo = int(rng.normal(phase["plyo_mean"], phase["plyo_std"]))

    return {
        "back_squat_working_max_kg": round(float(
            max_squat_kg * phase["intensity"] * daily_variance
        ), 1),
        "hang_power_clean_working_max_kg": round(float(
            max_hang_clean_kg * phase["intensity"] * daily_variance
        ), 1),
        "pullover_working_max_kg": round(float(
            max_pullover_kg * phase["intensity"] * daily_variance
        ), 1),
        "plyometric_foot_contacts": max(0, plyo),
    }


def build_kinematic_record(phase, rng):
    """generates runway kinematic metrics scaled by velocity modifier."""
    daily_variance = rng.normal(1.0, 0.015)
    vel = phase["velocity"]

    energy_transfer = round(float(
        rng.normal(baseline_energy_transfer_wkg * vel, 2.5)
    ), 1)

    return {
        "runup_velocity_cross_steps_ms": round(float(
            rng.normal(target_runup_velocity_ms * vel, 0.2)
        ), 2),
        "thorax_humerus_energy_transfer_rate_wkg": energy_transfer,
        "peak_release_velocity_ms": round(float(
            max_release_velocity_ms * vel * daily_variance
        ), 2),
        "avg_release_angle_deg": round(float(
            rng.normal(target_release_angle_deg, 1.0)
        ), 1),
        "avg_attack_angle_deg": round(float(
            rng.normal(target_attack_angle_deg, 0.5)
        ), 1),
    }


def build_readiness(week, rng):
    """generates physiological readiness markers for a given day."""
    hrv = float(np.clip(rng.normal(85, 8) + (week * 0.4), 40, 150))
    score = float(np.clip(rng.normal(80, 10) + (week * 0.5), 0, 100))

    return {
        "morning_hrv_rmssd": round(hrv, 1),
        "readiness_score_100": round(score, 1),
    }


def generate(start_date="2026-01-28", weeks=12, seed=42):
    """
    produces a 12-week daily telemetry stream for an elite male javelin thrower.
    outputs structured json to data/mock/javelin_telemetry_12wk.json.
    """
    rng = np.random.default_rng(seed)
    days = weeks * 7
    dates = [
        datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=i)
        for i in range(days)
    ]

    output = {
        "metadata": {
            "sport": "men's javelin",
            "athlete_profile": "elite (80m+ potential)",
            "generation_date": datetime.now().strftime("%Y-%m-%d"),
            "weeks": weeks,
            "seed": seed,
        },
        "telemetry_stream": [],
    }

    for i, current_date in enumerate(dates):
        week = (i // 7) + 1
        phase = resolve_phase(week)
        session = resolve_session(current_date.weekday())

        record = {
            "date": current_date.strftime("%Y-%m-%d"),
            "training_cycle": {
                "week": week,
                "periodization_phase": phase["name"],
                "session_type": session,
            },
            "physiological_readiness": build_readiness(week, rng),
            "gym_metrics": None,
            "kinematic_metrics": None,
        }

        if session == "gym_cns_plyometrics":
            record["gym_metrics"] = build_gym_record(phase, rng)
        elif session == "runway_technical":
            record["kinematic_metrics"] = build_kinematic_record(phase, rng)

        output["telemetry_stream"].append(record)

    base = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base, "..", "mock", "javelin_telemetry_12wk.json")
    output_path = os.path.normpath(output_path)

    with open(output_path, "w") as f:
        json.dump(output, f, indent=4)

    return output


if __name__ == "__main__":
    generate()
