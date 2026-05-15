"""
biomechanicals readiness integrator.
aggregates all 5 biomechanicals modules into a composite readiness score.
ref: biometrics project plan docs 1-5.
"""

from algorithms.biomechanicals.neural_sequencing import compute_proprioceptive_lag
from algorithms.biomechanicals.constraint_regressor import compute_kinematic_constraints
from algorithms.biomechanicals.power_profiler import compute_explosive_ceiling
from algorithms.biomechanicals.tissue_tolerance import compute_velocity_cap
from algorithms.biomechanicals.fatigue_horizon import compute_fatigue_horizon


def compute_biomechanicals_readiness(athlete):
    """
    runs all 5 biomechanicals modules and produces composite readiness.
    ref: biometrics project plan — biomechanicals integrator.
    """
    neural = compute_proprioceptive_lag(athlete)
    constraints = compute_kinematic_constraints(athlete)
    power = compute_explosive_ceiling(athlete)
    tissue = compute_velocity_cap(athlete)
    fatigue = compute_fatigue_horizon(athlete)

    neural_score = max(0.0, 100.0 - neural["predicted_lag_ms"] * 2.5)
    constraint_score = (constraints["achievable_rom_deg"] / constraints["baseline_rom_deg"]) * 100.0
    power_score = power["rfd_ceiling_percent"]
    tissue_score = (tissue["velocity_cap_ms"] / tissue["baseline_vmax_ms"]) * 100.0
    fatigue_score = (fatigue["predicted_reps_to_failure"] / fatigue["baseline_reps"]) * 100.0

    w_neural = 0.20
    w_constraint = 0.20
    w_power = 0.25
    w_tissue = 0.20
    w_fatigue = 0.15

    composite = (
        w_neural * neural_score
        + w_constraint * constraint_score
        + w_power * power_score
        + w_tissue * tissue_score
        + w_fatigue * fatigue_score
    )
    composite = max(0.0, min(100.0, composite))

    flags = []

    if neural["severity"] in ("severe", "moderate"):
        flags.append({
            "module": "neural_sequencing",
            "status": neural["severity"],
            "impact": f"{neural['predicted_lag_ms']}ms proprioceptive lag",
        })

    if constraints["severity"] in ("severe_restriction", "moderate_restriction"):
        flags.append({
            "module": "constraint_regressor",
            "status": constraints["severity"],
            "impact": f"{constraints['delta_rom_deg']} deg rom loss",
        })

    if power["status"] in ("catabolic_suppression", "reduced_drive"):
        flags.append({
            "module": "power_profiler",
            "status": power["status"],
            "impact": f"rfd at {power['rfd_ceiling_percent']}%",
        })

    if tissue["reflex_state"] in ("autonomic_reflex_breakdown", "protective_inhibition"):
        flags.append({
            "module": "tissue_tolerance",
            "status": tissue["reflex_state"],
            "impact": f"velocity cap {tissue['velocity_cap_ms']} m/s",
        })

    if fatigue["severity"] in ("critical", "restricted"):
        flags.append({
            "module": "fatigue_horizon",
            "status": fatigue["severity"],
            "impact": f"{fatigue['predicted_reps_to_failure']} reps to failure",
        })

    if composite >= 80:
        risk_level = "low"
    elif composite >= 65:
        risk_level = "moderate"
    elif composite >= 50:
        risk_level = "high"
    else:
        risk_level = "critical"

    result = {
        "algorithm": "biomechanicals_readiness",
        "biomechanicals_composite_score": round(composite, 2),
        "risk_level": risk_level,
        "sub_scores": {
            "neural_sequencing": round(neural_score, 2),
            "constraint_regressor": round(constraint_score, 2),
            "power_profiler": round(power_score, 2),
            "tissue_tolerance": round(tissue_score, 2),
            "fatigue_horizon": round(fatigue_score, 2),
        },
        "flags": flags,
        "flag_count": len(flags),
        "components": {
            "neural": neural,
            "constraints": constraints,
            "power": power,
            "tissue": tissue,
            "fatigue": fatigue,
        },
    }
    return result
