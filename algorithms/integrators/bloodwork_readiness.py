"""
bloodwork readiness integrator.
aggregates all 6 bloodwork kinetics modules into a composite readiness score.
ref: project plan doc 1 — biochemical attenuation factor (omega_bio).
"""

from algorithms.bloodwork.rbc_kinetics import run_rbc_kinetics
from algorithms.bloodwork.iron_kinetics import run_iron_kinetics
from algorithms.bloodwork.hormone_kinetics import run_hormone_kinetics
from algorithms.bloodwork.nutrient_kinetics import run_nutrient_kinetics
from algorithms.bloodwork.inflammation_kinetics import run_inflammation_kinetics
from algorithms.bloodwork.metabolic_kinetics import run_metabolic_kinetics

from config.settings import (
    ferritin_threshold,
    ck_threshold,
    hscrp_threshold,
    ftc_deficit_threshold,
    rho_hormonal_penalty,
    rho_iron_penalty,
    rho_muscle_penalty,
)


def compute_attenuation_factors(bloodwork):
    """
    computes multiplicative attenuation factors from bloodwork.
    ref: project plan doc 1 — omega_bio = rho_hormonal * rho_iron * rho_muscle.
    """
    hormonal = bloodwork.get("hormonal_panel", {})
    ft_ratio = hormonal.get("ft_cortisol_ratio", 1.0)
    ft_baseline = hormonal.get("ft_cortisol_ratio_baseline", 1.0)

    if ft_baseline > 0:
        ratio_deficit = (ft_baseline - ft_ratio) / ft_baseline
    else:
        ratio_deficit = 0.0

    if ratio_deficit > ftc_deficit_threshold:
        rho_h = rho_hormonal_penalty
    else:
        rho_h = 1.0

    iron = bloodwork.get("iron_panel", {})
    ferritin = iron.get("serum_ferritin_ng_ml", 100.0)

    if ferritin < ferritin_threshold:
        rho_i = rho_iron_penalty
    else:
        rho_i = 1.0

    inflammatory = bloodwork.get("inflammatory_recovery", {})
    ck = inflammatory.get("creatine_kinase_u_l", 0.0)
    hscrp = inflammatory.get("hscrp_mg_l", 0.0)

    if ck > ck_threshold and hscrp > hscrp_threshold:
        rho_m = rho_muscle_penalty
    else:
        rho_m = 1.0

    omega_bio = rho_h * rho_i * rho_m

    factors = {
        "rho_hormonal": rho_h,
        "rho_iron": rho_i,
        "rho_muscle": rho_m,
        "omega_bio": round(omega_bio, 4),
    }
    return omega_bio, factors


def compute_bloodwork_readiness(bloodwork):
    """
    runs all 6 bloodwork modules and produces composite readiness.
    ref: project plan flowchart — bloodwork integrator (readiness.py).
    """
    rbc_result = run_rbc_kinetics(bloodwork)
    iron_result = run_iron_kinetics(bloodwork)
    hormone_result = run_hormone_kinetics(bloodwork)
    nutrient_result = run_nutrient_kinetics(bloodwork)
    inflammation_result = run_inflammation_kinetics(bloodwork)
    metabolic_result = run_metabolic_kinetics(bloodwork)

    omega_bio, attenuation_factors = compute_attenuation_factors(bloodwork)

    bloodwork_score = omega_bio * 100.0

    flags = []

    if attenuation_factors["rho_iron"] < 1.0:
        flags.append({
            "marker": "ferritin",
            "status": "depleted",
            "impact": "aerobic capacity ceiling imposed",
        })

    if attenuation_factors["rho_hormonal"] < 1.0:
        flags.append({
            "marker": "ft_cortisol_ratio",
            "status": "catabolic",
            "impact": "overtraining risk elevated",
        })

    if attenuation_factors["rho_muscle"] < 1.0:
        flags.append({
            "marker": "ck_hscrp_combined",
            "status": "unresolved_damage",
            "impact": "sarcomere repair incomplete",
        })

    result = {
        "algorithm": "bloodwork_readiness",
        "bloodwork_score": round(bloodwork_score, 2),
        "omega_bio": round(omega_bio, 4),
        "attenuation_factors": attenuation_factors,
        "flags": flags,
        "flag_count": len(flags),
        "kinetics": {
            "rbc": rbc_result,
            "iron": iron_result,
            "hormones": hormone_result,
            "nutrients": nutrient_result,
            "inflammation": inflammation_result,
            "metabolic": metabolic_result,
        },
    }
    return result
