"""
master composite integrator.
final weighted aggregation of travel readiness, bloodwork readiness,
and biomechanics readiness.
outputs the master readiness score and serializes to master_output.json.
ref: project plan flowchart — master composite (master.py).
"""

import json
import os
from datetime import datetime


def compute_master_score(travel_result, bloodwork_result, biomechanics_result=None):
    """
    computes the final master readiness score.
    master = travel_composite * omega_bio * biomechanics_modifier.
    ref: project plan — the master readiness score directly reflects
    biological, logistical, environmental, and biomechanical load.
    """
    travel_score = travel_result["travel_composite_score"]
    omega_bio = bloodwork_result["omega_bio"]

    master_score = travel_score * omega_bio

    if biomechanics_result:
        biomech_modifier = biomechanics_result["biomechanics_composite_score"] / 100.0
        master_score = master_score * (0.6 + 0.4 * biomech_modifier)

    master_score = max(0.0, min(100.0, master_score))

    if master_score >= 80:
        protocol = "high_intensity_loading"
    elif master_score >= 65:
        protocol = "moderate_training"
    elif master_score >= 50:
        protocol = "taper_recovery"
    else:
        protocol = "rest_rehabilitation"

    return round(master_score, 2), protocol


def compile_master_output(athlete, travel_result, bloodwork_result, output_path,
                          biomechanics_result=None):
    """
    compiles all algorithm outputs into a single master output file.
    ref: project plan — all outputs compiled into master file.
    """
    master_score, protocol = compute_master_score(
        travel_result, bloodwork_result, biomechanics_result
    )

    master_output = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "z",
            "athlete_id": athlete.bio.get("athlete_id", "unknown"),
            "athlete_name": athlete.bio.get("name", "unknown"),
            "pipeline_version": "2.0.0",
        },
        "master_readiness": {
            "score": master_score,
            "protocol_recommendation": protocol,
            "travel_composite": travel_result["travel_composite_score"],
            "bloodwork_composite": bloodwork_result["bloodwork_score"],
            "omega_bio": bloodwork_result["omega_bio"],
            "risk_level": travel_result["risk_level"],
        },
        "travel": travel_result,
        "bloodwork": bloodwork_result,
        "athlete_summary": {
            "name": athlete.bio.get("name"),
            "sport": athlete.bio.get("sport"),
            "weight_kg": athlete.bio.get("weight_kg"),
            "destination": athlete.travel["destination"].get("city"),
            "timezone_shift": athlete.timezone_shift(),
            "direction": athlete.direction(),
            "flight_duration_hours": athlete.travel["flight"]["duration_hours"],
        },
    }

    if biomechanics_result:
        master_output["master_readiness"]["biomechanics_composite"] = (
            biomechanics_result["biomechanics_composite_score"]
        )
        master_output["master_readiness"]["biomechanics_protocol"] = (
            biomechanics_result["protocol_recommendation"]
        )
        master_output["biomechanics"] = biomechanics_result

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(master_output, f, indent=2, default=str)

    return master_output
