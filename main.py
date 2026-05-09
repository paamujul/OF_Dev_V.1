"""
main entry point — orchestrates the full athlete wellness pipeline.
loads mock data, runs all algorithms, compiles master output,
and generates ai-powered recommendations.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_struct.athlete_profile import load_athlete
from algorithms.integrators.travel_readiness import compute_travel_readiness
from algorithms.integrators.bloodwork_readiness import compute_bloodwork_readiness
from algorithms.integrators.biomechanics_readiness import compute_biomechanics_readiness
from algorithms.integrators.master_composite import compile_master_output
from algorithms.ai.recommendation_engine import run_recommendation_engine


def get_data_paths():
    """returns absolute paths to all mock data files."""
    base = os.path.dirname(os.path.abspath(__file__))
    paths = {
        "bio": os.path.join(base, "data", "mock", "athlete_bio.json"),
        "wearable": os.path.join(base, "data", "mock", "wearable_data.json"),
        "bloodwork": os.path.join(base, "data", "mock", "bloodwork_panels.json"),
        "travel": os.path.join(base, "data", "mock", "travel_scenario.json"),
        "emg": os.path.join(base, "data", "mock", "emg_session_data.json"),
        "muscle_arch": os.path.join(base, "data", "mock", "muscle_architecture.json"),
    }
    return paths


def run_pipeline():
    """executes the full algorithm pipeline end to end."""
    paths = get_data_paths()

    print("loading athlete data...")
    athlete = load_athlete(
        bio_path=paths["bio"],
        wearable_path=paths["wearable"],
        bloodwork_path=paths["bloodwork"],
        travel_path=paths["travel"],
        emg_path=paths["emg"],
        muscle_arch_path=paths["muscle_arch"],
    )
    print(f"  athlete: {athlete.bio['name']}")
    print(f"  destination: {athlete.travel['destination']['city']}")
    print(f"  timezone shift: {athlete.timezone_shift()} hours {athlete.direction()}")

    print("\nrunning travel algorithms...")
    travel_result = compute_travel_readiness(athlete)
    print(f"  pretravel readiness: {travel_result['components']['pretravel']['r_total']}")
    print(f"  travel degradation: {travel_result['components']['degradation']['predicted_readiness_drop_percent']}%")
    print(f"  thermoregulatory power: {travel_result['components']['thermoregulatory']['expected_power_percent']}%")
    print(f"  circadian adaptation days: {travel_result['components']['circadian']['total_adaptation_days']}")
    print(f"  travel composite: {travel_result['travel_composite_score']}")

    print("\nrunning bloodwork algorithms...")
    bloodwork_result = compute_bloodwork_readiness(athlete.bloodwork)
    print(f"  bloodwork score: {bloodwork_result['bloodwork_score']}")
    print(f"  omega_bio: {bloodwork_result['omega_bio']}")
    print(f"  clinical flags: {bloodwork_result['flag_count']}")

    print("\nrunning biomechanics algorithms...")
    biomechanics_result = compute_biomechanics_readiness(athlete)
    print(f"  biomechanics composite: {biomechanics_result['biomechanics_composite_score']}")
    print(f"  protocol: {biomechanics_result['protocol_recommendation']}")
    print(f"  biomechanics flags: {biomechanics_result['flag_count']}")
    for key, score in biomechanics_result["component_scores"].items():
        print(f"    {key}: {score}")

    print("\ncompiling master output...")
    base = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base, "outputs", "master_output.json")

    master = compile_master_output(
        athlete, travel_result, bloodwork_result, output_path,
        biomechanics_result=biomechanics_result,
    )

    print(f"\n{'=' * 50}")
    print(f"  master readiness score: {master['master_readiness']['score']}")
    print(f"  protocol: {master['master_readiness']['protocol_recommendation']}")
    print(f"  risk level: {master['master_readiness']['risk_level']}")
    print(f"{'=' * 50}")
    print(f"\nmaster output written to: {output_path}")

    print("\ngenerating ai recommendations...")
    ai_result = run_recommendation_engine(master)

    if ai_result["status"] == "generated":
        print(f"  model: {ai_result['model']}")
        print(f"  output: {ai_result.get('output_path', 'n/a')}")
        print(f"\n{'=' * 50}")
        print("  athlete protocols")
        print(f"{'=' * 50}")
        print(f"\n{ai_result['recommendations']}")
    elif ai_result["status"] == "skipped":
        print(f"  skipped: {ai_result['reason']}")
        print("  set GEMINI_API_KEY environment variable to enable")

    master["ai_recommendations"] = ai_result
    return master


if __name__ == "__main__":
    run_pipeline()
