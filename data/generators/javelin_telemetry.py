"""
12-week hierarchical micro-exercise generator for an elite male javelin thrower.
"""

import os
import json
import numpy as np
from datetime import datetime, timedelta


def resolve_phase(week_num):
    """returns periodization parameters based on training week."""
    if week_num <= 4:
        return {
            "name": "base_hypertrophy",
            "intensity_mod": 0.80,
            "acc_volume": "4x10",
            "plyo_dist": {"depth jumps": 20, "pogo hops": 60, "broad jumps": 40},
        }
    elif week_num <= 8:
        return {
            "name": "maximal_strength",
            "intensity_mod": 0.90,
            "acc_volume": "3x6",
            "plyo_dist": {"depth jumps": 15, "pogo hops": 40, "broad jumps": 25},
        }
    return {
        "name": "peaking_taper",
        "intensity_mod": 0.98,
        "acc_volume": "2x4",
        "plyo_dist": {"depth jumps": 10, "pogo hops": 20, "broad jumps": 10},
    }


def build_lift_hierarchy(lift_key, baselines, phase, daily_variance):
    """generates micro payloads for a given lift key based on periodization phase."""
    intensity_mod = phase["intensity_mod"]
    primary_weight = round(float(
        baselines[lift_key]["primary"] * intensity_mod * daily_variance
    ), 1)

    accessories = []
    num_accessories = 2 if phase["name"] == "peaking_taper" else 3

    for acc in baselines[lift_key]["accessories"][:num_accessories]:
        acc_weight = round(float(
            baselines[lift_key]["primary"] * acc["ratio"] * intensity_mod * daily_variance
        ), 1)
        accessories.append({
            "movement": acc["name"].lower(),
            "working_weight_kg": acc_weight,
            "prescribed_volume": phase["acc_volume"]
        })

    return {
        "primary_target_kg": primary_weight,
        "compounding_accessories": accessories
    }


def generate(start_date="2026-01-28", weeks=12, seed=42):
    """
    produces a 12-week daily telemetry stream for an elite male javelin thrower.
    outputs structured json to data/mock/elite_javelin_micro_gym_data.json.
    """
    rng = np.random.default_rng(seed)
    days = weeks * 7
    dates = [
        datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=i)
        for i in range(days)
    ]

    baselines = {
        "back_squat": {
            "primary": 190.0,
            "accessories": [
                {"name": "bulgarian split squat", "ratio": 0.45},
                {"name": "leg press", "ratio": 1.2},
                {"name": "weighted plank", "ratio": 0.25},
            ]
        },
        "hang_power_clean": {
            "primary": 128.8,
            "accessories": [
                {"name": "romanian deadlift (rdl)", "ratio": 1.1},
                {"name": "heavy kb swings", "ratio": 0.35},
                {"name": "glute-ham raise", "ratio": 0.15},
            ]
        },
        "pullover": {
            "primary": 110.0,
            "accessories": [
                {"name": "lat pulldown", "ratio": 0.95},
                {"name": "seated cable row", "ratio": 0.90},
                {"name": "face pulls", "ratio": 0.30},
            ]
        }
    }

    output_data = {"telemetry_stream": []}

    for i, current_date in enumerate(dates):
        week_num = (i // 7) + 1
        phase = resolve_phase(week_num)

        day_of_week = current_date.weekday()
        if day_of_week in [0, 2, 4]:
            session_type = "gym_cns_and_accessories"
            daily_variance = float(rng.normal(1.0, 0.02))

            gym_payload = {
                "lower_body_push_complex": build_lift_hierarchy(
                    "back_squat", baselines, phase, daily_variance
                ),
                "posterior_chain_explosive_complex": build_lift_hierarchy(
                    "hang_power_clean", baselines, phase, daily_variance
                ),
                "thoracic_lat_complex": build_lift_hierarchy(
                    "pullover", baselines, phase, daily_variance
                ),
                "plyometric_distribution": phase["plyo_dist"]
            }
        elif day_of_week in [1, 3, 5]:
            session_type = "runway_technical"
            gym_payload = None
        else:
            session_type = "recovery"
            gym_payload = None

        day_record = {
            "date": current_date.strftime("%Y-%m-%d"),
            "training_cycle": {
                "week": week_num,
                "periodization_phase": phase["name"],
                "session_type": session_type
            },
            "gym_session_breakdown": gym_payload
        }

        output_data["telemetry_stream"].append(day_record)

    base = os.path.dirname(os.path.abspath(__file__))
    output_filename = os.path.join(base, "..", "mock", "elite_javelin_micro_gym_data.json")
    output_filename = os.path.normpath(output_filename)

    with open(output_filename, "w") as outfile:
        json.dump(output_data, outfile, indent=4)

    print(f"generated hierarchical micro-exercise json into '{output_filename}'")
    return output_data


if __name__ == "__main__":
    generate()
