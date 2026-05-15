"""
backtest with continuous bloodwork attenuation.
replaces binary penalty flags with sigmoid-based continuous scoring
to introduce realistic variance in the bloodwork readiness output.
"""

import sys
import os
import json
import math
import statistics
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_struct.athlete_profile import load_athlete
from algorithms.integrators.travel_readiness import compute_travel_readiness
from algorithms.integrators.biomechanicals_readiness import compute_biomechanicals_readiness
from algorithms.bloodwork.rbc_kinetics import run_rbc_kinetics
from algorithms.bloodwork.iron_kinetics import run_iron_kinetics
from algorithms.bloodwork.hormone_kinetics import run_hormone_kinetics
from algorithms.bloodwork.nutrient_kinetics import run_nutrient_kinetics
from algorithms.bloodwork.inflammation_kinetics import run_inflammation_kinetics
from algorithms.bloodwork.metabolic_kinetics import run_metabolic_kinetics
from algorithms.integrators.master_composite import compile_master_output

from config.settings import (
    ferritin_threshold,
    ck_threshold,
    hscrp_threshold,
    ftc_deficit_threshold,
)


def sigmoid_penalty(value, threshold, steepness=10.0, direction="below"):
    """
    continuous sigmoid penalty that smoothly transitions from 1.0 (healthy)
    to ~0.7 (penalized) as the value crosses the threshold.
    direction='below' penalizes values below threshold (e.g. ferritin).
    direction='above' penalizes values above threshold (e.g. CK, hs-CRP).
    """
    if direction == "below":
        x = (threshold - value) / threshold
    else:
        x = (value - threshold) / threshold

    penalty = 1.0 / (1.0 + math.exp(-steepness * x))
    # scale so penalty ranges from 1.0 (healthy) to 0.7 (penalized)
    return 1.0 - 0.3 * penalty


def compute_continuous_bloodwork(bloodwork):
    """
    continuous attenuation bloodwork scoring.
    replaces the binary rho flags with smooth sigmoid curves.
    """
    # run all kinetics (for completeness)
    run_rbc_kinetics(bloodwork)
    run_iron_kinetics(bloodwork)
    run_hormone_kinetics(bloodwork)
    run_nutrient_kinetics(bloodwork)
    run_inflammation_kinetics(bloodwork)
    run_metabolic_kinetics(bloodwork)

    # hormonal: continuous penalty based on fT/cortisol ratio deficit
    hormonal = bloodwork.get("hormonal_panel", {})
    ft_ratio = hormonal.get("ft_cortisol_ratio", 1.0)
    ft_baseline = hormonal.get("ft_cortisol_ratio_baseline", 1.0)
    if ft_baseline > 0:
        ratio_deficit = (ft_baseline - ft_ratio) / ft_baseline
    else:
        ratio_deficit = 0.0
    # sigmoid around the deficit threshold
    rho_h = sigmoid_penalty(ratio_deficit, ftc_deficit_threshold, steepness=15.0, direction="above")

    # iron: continuous penalty based on ferritin level
    iron = bloodwork.get("iron_panel", {})
    ferritin = iron.get("serum_ferritin_ng_ml", 100.0)
    rho_i = sigmoid_penalty(ferritin, ferritin_threshold, steepness=8.0, direction="below")

    # inflammation: continuous penalty based on CK level
    inflammatory = bloodwork.get("inflammatory_recovery", {})
    ck = inflammatory.get("creatine_kinase_u_l", 0.0)
    hscrp = inflammatory.get("hscrp_mg_l", 0.0)
    rho_ck = sigmoid_penalty(ck, ck_threshold, steepness=5.0, direction="above")
    rho_crp = sigmoid_penalty(hscrp, hscrp_threshold, steepness=8.0, direction="above")
    rho_m = (rho_ck + rho_crp) / 2.0

    # nutritional: continuous penalty based on vitamin D distance from optimal
    nutritional = bloodwork.get("nutritional_panel", {})
    vit_d = nutritional.get("vitamin_d_ng_ml", 40.0)
    # optimal = 40-60, penalize below 30
    rho_n = sigmoid_penalty(vit_d, 30.0, steepness=6.0, direction="below")

    # metabolic: continuous penalty based on glucose regulation
    metabolic = bloodwork.get("metabolic_panel", {})
    glucose = metabolic.get("fasting_glucose_mg_dl", 90.0)
    # penalize above 100 (pre-diabetic threshold)
    rho_g = sigmoid_penalty(glucose, 100.0, steepness=5.0, direction="above")

    omega_bio = rho_h * rho_i * rho_m * rho_n * rho_g
    bloodwork_score = omega_bio * 100.0

    return {
        "bloodwork_score": round(bloodwork_score, 2),
        "omega_bio": round(omega_bio, 4),
        "attenuation_factors": {
            "rho_hormonal": round(rho_h, 4),
            "rho_iron": round(rho_i, 4),
            "rho_muscle": round(rho_m, 4),
            "rho_nutritional": round(rho_n, 4),
            "rho_glucose": round(rho_g, 4),
        },
        "flags": [],
        "flag_count": 0,
        "kinetics": {},
    }


def run_backtest():
    master_path = 'data/master/master_athlete_profiles.json'
    with open(master_path, 'r') as f:
        master_data = json.load(f)

    print(f"Running continuous-attenuation backtest on {len(master_data)} athletes...")
    travel_scores = []
    bloodwork_scores = []
    biomech_scores = []
    master_scores = []

    for i, athlete_data in enumerate(master_data):
        day = athlete_data['history'][-1]
        history = athlete_data['history'][-30:]
        bio = athlete_data['bio']
        bio['name'] = athlete_data['id']

        wearable = {}
        wearable['hrv_rmssd_30d'] = [d['wearables']['hrv_rmssd'] for d in history]
        wearable['sleep_efficiency_7d'] = [d['wearables']['sleep_efficiency'] for d in history[-7:]]
        wearable['total_sleep_time_7d'] = [d['wearables']['total_sleep_time'] for d in history[-7:]]
        wearable['deep_sleep_percent_7d'] = [d['wearables']['deep_sleep_percent'] for d in history[-7:]]
        wearable['rem_percent_7d'] = [d['wearables']['rem_sleep_percent'] for d in history[-7:]]
        wearable['deep_rem_percent_7d'] = [d['wearables']['deep_sleep_percent'] + d['wearables']['rem_sleep_percent'] for d in history[-7:]]
        wearable['skin_temp_celsius_7d'] = [d['wearables']['night_skin_temp'] for d in history[-7:]]
        wearable['resting_hr_7d'] = [d['wearables']['resting_hr'] for d in history[-7:]]
        wearable['spo2_7d'] = [d['wearables']['spo2'] for d in history[-7:]]
        wearable['respiratory_rate_7d'] = [14.0 for _ in history[-7:]]
        wearable['sleep_debt_3d_hours'] = 1.5
        wearable['nighttime_skin_temp'] = day['wearables']['night_skin_temp']
        wearable['nighttime_rhr'] = day['wearables']['resting_hr']
        wearable['spo2_baseline'] = sum(wearable['spo2_7d'])/len(wearable['spo2_7d'])
        wearable['spo2_transit'] = day['travel']['spo2_flight']
        wearable['strain_last_session'] = 14.0
        wearable['hr_zone_minutes'] = {'zone4': 10, 'zone5': 5}
        wearable['peak_strain_hour'] = 15.0
        wearable['active_minutes_inflight'] = 20.0
        wearable['session_duration_minutes'] = 90.0
        wearable['active_energy_kcal_last_session'] = 800.0
        wearable['active_hr_bpm_last_session'] = 130.0

        bloodwork = {}
        bloodwork['cbc'] = {'rbc_count_million_per_ul': day['bloodwork']['hematology']['rbc_count']}
        bloodwork['epo'] = {'epo_miu_ml': day['bloodwork']['hematology']['epo']}
        bloodwork['iron_panel'] = {
            'serum_ferritin_ng_ml': day['bloodwork']['iron_panel']['ferritin'],
            'tibc_ug_dl': day['bloodwork']['iron_panel']['tibc']
        }
        cort = max(0.1, day['bloodwork']['hormonal']['cortisol'] / 27.59)
        bloodwork['hormonal_panel'] = {
            'cortisol_ug_dl': cort,
            'free_testosterone_pg_ml': day['bloodwork']['hormonal']['free_testosterone'],
            'ft_cortisol_ratio': day['bloodwork']['hormonal']['free_testosterone'] / cort,
            'ft_cortisol_ratio_baseline': (day['bloodwork']['hormonal']['free_testosterone'] / cort) * 1.1
        }
        bloodwork['metabolic_panel'] = {
            'fasting_glucose_mg_dl': day['bloodwork']['metabolic']['fasting_glucose'],
            'fasting_insulin_uiu_ml': day['bloodwork']['metabolic']['fasting_insulin'],
            'hba1c_percent': day['bloodwork']['metabolic']['hba1c']
        }
        bloodwork['inflammatory_recovery'] = {
            'hscrp_mg_l': day['bloodwork']['inflammation']['hscrp'],
            'creatine_kinase_u_l': day['bloodwork']['inflammation']['creatine_kinase']
        }
        bloodwork['nutritional_panel'] = {
            'vitamin_d_ng_ml': day['bloodwork']['nutritional']['vitamin_d'],
            'vitamin_b12_pg_ml': 600.0,
            'magnesium_mg_dl': 2.1,
            'zinc_ug_dl': 90.0,
            'folate_ng_ml': 15.0
        }

        travel = {
            'flight': {
                'timezone_shift': day['travel']['timezone_shift'],
                'direction': 'east',
                'duration_hours': day['travel']['flight_duration']
            },
            'origin': {'altitude_m': 100.0},
            'destination': {
                'altitude_m': 100.0,
                'temp_c': day['travel']['destination_temp_c'],
                'humidity_percent': 50.0,
                'wind_speed_m_s': 2.0,
                'solar_radiation_w_m2': 400.0,
                'city': 'TestCity'
            },
            'event': {
                'arrival_days_before_event': 5.0
            }
        }

        os.makedirs('data/temp_backtest', exist_ok=True)
        with open('data/temp_backtest/b.json', 'w') as f: json.dump(bio, f)
        with open('data/temp_backtest/w.json', 'w') as f: json.dump(wearable, f)
        with open('data/temp_backtest/bl.json', 'w') as f: json.dump(bloodwork, f)
        with open('data/temp_backtest/t.json', 'w') as f: json.dump(travel, f)

        athlete = load_athlete('data/temp_backtest/b.json', 'data/temp_backtest/w.json', 'data/temp_backtest/bl.json', 'data/temp_backtest/t.json')

        t_res = compute_travel_readiness(athlete)
        b_res = compute_continuous_bloodwork(athlete.bloodwork)
        m_res = compute_biomechanicals_readiness(athlete)

        # compute master score using same weights as master_composite.py
        travel_adjusted = t_res['travel_composite_score'] * b_res['omega_bio']
        master = (0.40 * travel_adjusted + 0.35 * m_res['biomechanicals_composite_score'] + 0.25 * b_res['bloodwork_score'])
        master = max(0.0, min(100.0, master))

        travel_scores.append(t_res['travel_composite_score'])
        bloodwork_scores.append(b_res['bloodwork_score'])
        biomech_scores.append(m_res['biomechanicals_composite_score'])
        master_scores.append(round(master, 2))

    os.makedirs('outputs/plots', exist_ok=True)

    plt.figure(figsize=(10, 6))
    plt.boxplot([travel_scores, bloodwork_scores, biomech_scores], tick_labels=['Travel', 'Bloodwork', 'Biomech'])
    plt.title('Algorithm Suite Readiness Score Variance (Continuous Bloodwork)')
    plt.ylabel('Score (0-100)')
    plt.savefig('outputs/plots/backtest_suite_variance_continuous.png')
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.hist(master_scores, bins=20, color='blue', alpha=0.7)
    plt.axvline(statistics.mean(master_scores), color='red', linestyle='dashed', linewidth=2, label=f"Mean: {statistics.mean(master_scores):.1f}")
    plt.title('Distribution of Global Readiness Scores (Continuous Bloodwork)')
    plt.xlabel('Master Composite Score')
    plt.ylabel('Frequency')
    plt.legend()
    plt.savefig('outputs/plots/backtest_global_distribution_continuous.png')
    plt.close()

    print("Backtest complete.")
    print(f"Master  — Mean: {statistics.mean(master_scores):.2f}, StdDev: {statistics.stdev(master_scores):.2f}")
    print(f"Travel  — Mean: {statistics.mean(travel_scores):.2f}, StdDev: {statistics.stdev(travel_scores):.2f}")
    print(f"Blood   — Mean: {statistics.mean(bloodwork_scores):.2f}, StdDev: {statistics.stdev(bloodwork_scores):.2f}")
    print(f"Biomech — Mean: {statistics.mean(biomech_scores):.2f}, StdDev: {statistics.stdev(biomech_scores):.2f}")


if __name__ == "__main__":
    run_backtest()

