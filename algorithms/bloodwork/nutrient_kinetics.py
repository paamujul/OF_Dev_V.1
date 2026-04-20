"""
nutrient absorption kinetics via michaelis-menten enzyme model.
ref: project plan flowchart — hyperbolic saturation curves.
"""

import numpy as np

from config.settings import (
    default_vmax,
    default_km,
)


def michaelis_menten_rate(substrate, vmax, km):
    """
    michaelis-menten equation for enzymatic absorption rate.
    v = vmax * s / (km + s)
    ref: project plan flowchart — michaelis-menten enzyme kinetics.
    """
    if (km + substrate) == 0:
        return 0.0
    rate = (vmax * substrate) / (km + substrate)
    return rate


def compute_absorption_curve(substrate_doses, vmax, km):
    """
    generates absorption rate curve across a range of doses.
    demonstrates diminishing returns at high doses.
    """
    rates = []
    efficiencies = []

    for dose in substrate_doses:
        rate = michaelis_menten_rate(dose, vmax, km)
        rates.append(round(rate, 4))

        if dose > 0:
            efficiency = rate / dose
        else:
            efficiency = 0.0
        efficiencies.append(round(efficiency, 4))

    half_max_dose = km
    saturation_90_dose = km * 9

    result = {
        "doses": substrate_doses.tolist() if hasattr(substrate_doses, 'tolist') else list(substrate_doses),
        "absorption_rates": rates,
        "efficiencies": efficiencies,
        "half_max_dose": half_max_dose,
        "saturation_90_dose": saturation_90_dose,
        "vmax": vmax,
        "km": km,
    }
    return result


def simulate_nutrient_kinetics(substrate_doses, vmax, km, nutrient_name="generic"):
    """
    full nutrient kinetics simulation.
    ref: project plan — proves via hyperbolic saturation curves why massive
    micronutrient dosing leads to diminishing returns and excretion.
    """
    curve = compute_absorption_curve(substrate_doses, vmax, km)

    optimal_dose = km * 2
    optimal_rate = michaelis_menten_rate(optimal_dose, vmax, km)

    curve["algorithm"] = "nutrient_kinetics"
    curve["nutrient"] = nutrient_name
    curve["optimal_dose"] = optimal_dose
    curve["optimal_absorption_rate"] = round(optimal_rate, 4)

    return curve


def run_nutrient_kinetics(bloodwork):
    """
    runs nutrient kinetics for key micronutrients from bloodwork data.
    """
    nutritional = bloodwork.get("nutritional_panel", {})

    dose_range = np.linspace(0, 500, 50)

    nutrient_configs = {
        "vitamin_d": {"vmax": 80.0, "km": 40.0, "current": nutritional.get("vitamin_d_ng_ml", 30)},
        "vitamin_b12": {"vmax": 120.0, "km": 60.0, "current": nutritional.get("vitamin_b12_pg_ml", 400)},
        "magnesium": {"vmax": 90.0, "km": 45.0, "current": nutritional.get("magnesium_mg_dl", 2.0)},
        "folate": {"vmax": 70.0, "km": 35.0, "current": nutritional.get("folate_ng_ml", 10)},
        "zinc": {"vmax": 85.0, "km": 42.0, "current": nutritional.get("zinc_ug_dl", 80)},
    }

    results = {
        "algorithm": "nutrient_kinetics",
        "nutrients": {},
    }

    for name, cfg in nutrient_configs.items():
        kinetics = simulate_nutrient_kinetics(
            substrate_doses=dose_range,
            vmax=cfg["vmax"],
            km=cfg["km"],
            nutrient_name=name,
        )
        kinetics["current_level"] = cfg["current"]
        results["nutrients"][name] = kinetics

    return results
