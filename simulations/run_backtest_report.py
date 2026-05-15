import sys
import os
import json
import statistics
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_struct.athlete_profile import load_athlete
from algorithms.integrators.master_composite import compile_master_output
from algorithms.integrators.travel_readiness import compute_travel_readiness
from algorithms.integrators.bloodwork_readiness import compute_bloodwork_readiness
from algorithms.integrators.biomechanicals_readiness import compute_biomechanicals_readiness

def run_backtest():
    master_path = 'data/master/master_athlete_profiles.json'
    with open(master_path, 'r') as f:
        master_data = json.load(f)
        
    print(f"Running backtest on {len(master_data)} athletes...")
    scores = []
    travel_scores = []
    bloodwork_scores = []
    biomech_scores = []
    
    for i, athlete_data in enumerate(master_data):
        # We wrote a helper script earlier that generated data/backtest files for the first athlete
        # But we want to run all 100 directly. 
        # Since load_athlete reads files, we will write temp files for each and process.
        
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
        b_res = compute_bloodwork_readiness(athlete.bloodwork)
        m_res = compute_biomechanicals_readiness(athlete)
        
        master = compile_master_output(athlete, t_res, b_res, m_res, 'data/temp_backtest/out.json')
        
        scores.append(master['master_readiness']['score'])
        travel_scores.append(t_res['travel_composite_score'])
        bloodwork_scores.append(b_res['bloodwork_score'])
        biomech_scores.append(m_res['biomechanicals_composite_score'])

    os.makedirs('outputs/plots', exist_ok=True)
    
    plt.figure(figsize=(10,6))
    plt.hist(scores, bins=20, color='blue', alpha=0.7)
    plt.axvline(statistics.mean(scores), color='red', linestyle='dashed', linewidth=2, label=f"Mean: {statistics.mean(scores):.1f}")
    plt.title('Distribution of Global Readiness Scores (100 Synthetic Athletes)')
    plt.xlabel('Master Composite Score')
    plt.ylabel('Frequency')
    plt.legend()
    plt.savefig('outputs/plots/backtest_global_distribution.png')
    plt.close()

    plt.figure(figsize=(10,6))
    plt.boxplot([travel_scores, bloodwork_scores, biomech_scores], labels=['Travel', 'Bloodwork', 'Biomech'])
    plt.title('Algorithm Suite Readiness Score Variance')
    plt.ylabel('Score (0-100)')
    plt.savefig('outputs/plots/backtest_suite_variance.png')
    plt.close()

    print("Backtest complete. Plots generated in outputs/plots.")
    print(f"Mean Master Score: {statistics.mean(scores):.2f}")
    print(f"Mean Travel Score: {statistics.mean(travel_scores):.2f}")
    print(f"Mean Bloodwork Score: {statistics.mean(bloodwork_scores):.2f}")
    print(f"Mean Biomech Score: {statistics.mean(biomech_scores):.2f}")

if __name__ == "__main__":
    run_backtest()
