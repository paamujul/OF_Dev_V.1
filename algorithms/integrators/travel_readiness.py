"""
travel readiness integrator.
aggregates all 4 travel algorithm modules into a unified travel readiness score.
ref: project plan docs 1-4.
"""

from algorithms.travel.pretravel_readiness import compute_pretravel_score
from algorithms.travel.travel_degradation import compute_travel_degradation
from algorithms.travel.thermoregulatory import compute_expected_power
from algorithms.travel.circadian_shift import generate_zeitgeber_schedule


def compute_travel_readiness(athlete):
    """
    runs all 4 travel modules and produces composite travel readiness.
    ref: project plan flowchart — master composite integrator.
    """
    pretravel = compute_pretravel_score(athlete)
    degradation = compute_travel_degradation(athlete)
    thermoreg = compute_expected_power(athlete)

    tz_shift = athlete.timezone_shift()
    direction = athlete.direction()
    tmin = athlete.bio.get("tmin_hour", 5.0)
    circadian = generate_zeitgeber_schedule(tz_shift, direction, tmin)

    pretravel_score = pretravel["r_total"]
    degradation_drop = degradation["predicted_readiness_drop_percent"]
    thermoreg_score = thermoreg["expected_power_percent"]

    post_travel_readiness = pretravel_score * (1.0 - degradation_drop / 100.0)
    post_travel_readiness = max(0.0, min(100.0, post_travel_readiness))

    components = [post_travel_readiness, thermoreg_score]
    travel_composite = sum(components) / len(components)

    risk_level = "low"
    if travel_composite < 50:
        risk_level = "critical"
    elif travel_composite < 65:
        risk_level = "high"
    elif travel_composite < 80:
        risk_level = "moderate"

    result = {
        "algorithm": "travel_readiness",
        "travel_composite_score": round(travel_composite, 2),
        "post_travel_readiness": round(post_travel_readiness, 2),
        "risk_level": risk_level,
        "components": {
            "pretravel": pretravel,
            "degradation": degradation,
            "thermoregulatory": thermoreg,
            "circadian": circadian,
        },
    }
    return result
