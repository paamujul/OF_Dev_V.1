"""
end-to-end smoke test for the full athlete wellness pipeline.
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_full_pipeline():
    """validates full pipeline execution and output structure."""
    from main import run_pipeline

    master = run_pipeline()

    assert master is not None
    assert "master_readiness" in master
    assert "travel" in master
    assert "bloodwork" in master
    assert "meta" in master
    assert "athlete_summary" in master

    score = master["master_readiness"]["score"]
    assert 0 <= score <= 100

    assert master["master_readiness"]["protocol_recommendation"] in [
        "high_intensity_loading",
        "moderate_training",
        "taper_recovery",
        "rest_rehabilitation",
    ]

    assert master["master_readiness"]["risk_level"] in [
        "low", "moderate", "high", "critical",
    ]


def test_travel_components():
    """validates travel subsystem outputs."""
    from data_struct.athlete_profile import load_athlete
    from algorithms.integrators.travel_readiness import compute_travel_readiness

    base = os.path.join(os.path.dirname(__file__), "..")
    athlete = load_athlete(
        os.path.join(base, "data", "mock", "athlete_bio.json"),
        os.path.join(base, "data", "mock", "wearable_data.json"),
        os.path.join(base, "data", "mock", "bloodwork_panels.json"),
        os.path.join(base, "data", "mock", "travel_scenario.json"),
    )

    result = compute_travel_readiness(athlete)

    assert "pretravel" in result["components"]
    assert "degradation" in result["components"]
    assert "thermoregulatory" in result["components"]
    assert "circadian" in result["components"]

    assert 0 <= result["travel_composite_score"] <= 100
    assert result["components"]["pretravel"]["r_total"] >= 0
    assert result["components"]["thermoregulatory"]["expected_power_percent"] >= 0


def test_bloodwork_components():
    """validates bloodwork subsystem outputs."""
    from algorithms.integrators.bloodwork_readiness import compute_bloodwork_readiness

    base = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(base, "data", "mock", "bloodwork_panels.json"), "r") as f:
        bloodwork = json.load(f)

    result = compute_bloodwork_readiness(bloodwork)

    assert "kinetics" in result
    assert "rbc" in result["kinetics"]
    assert "iron" in result["kinetics"]
    assert "hormones" in result["kinetics"]
    assert "nutrients" in result["kinetics"]
    assert "inflammation" in result["kinetics"]
    assert "metabolic" in result["kinetics"]

    assert 0 <= result["bloodwork_score"] <= 100
    assert 0 <= result["omega_bio"] <= 1.0


def test_output_file_written():
    """validates that master_output.json is created and valid."""
    from main import run_pipeline

    run_pipeline()

    base = os.path.join(os.path.dirname(__file__), "..")
    output_path = os.path.join(base, "outputs", "master_output.json")

    assert os.path.exists(output_path)

    with open(output_path, "r") as f:
        data = json.load(f)

    assert "master_readiness" in data
    assert "score" in data["master_readiness"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
