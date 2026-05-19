"""
global constants and coefficients for the athlete wellness pipeline.
sources: project plan docs 1-4.
"""

"""hrv / wearable windows"""
# ref: plews et al. (2013), sports medicine
hrv_long_window = 28
hrv_short_window = 7
min_readings_req = 3

# wearable baseline weights (doc 1)
w_ans = 0.60
w_slp = 0.40

"""autonomic readiness thresholds (doc 1 — updated)"""
# ref: buchheit (2014), frontiers in physiology
# ref: miller et al. (2020), bmj open sport & exercise medicine
z_hrv_optimal_low = -0.5
z_hrv_optimal_high = 0.5
z_hrv_hyperactivity_threshold = 1.5
z_rhr_hyperactivity_threshold = -1.0
hyperactivity_cap = 80
ans_hrv_penalty_weight = 10
ans_rhr_penalty_weight = 10
ans_rr_penalty_weight = 20
z_rr_severe_threshold = 1.0

"""sleep readiness thresholds (doc 1 — updated)"""
# ref: fullagar et al. (2015), sports medicine
# ref: simpson et al. (2017), scand j med sci sports
# ref: kellmann et al. (2018), ijspp
sleep_efficiency_target = 85.0
total_sleep_time_target = 7.5
sleep_tst_cap = 8.0
sleep_debt_threshold_hours = 1.5
sleep_debt_penalty = 0.85
deep_rem_minimum_percent = 30.0
architecture_penalty = 0.90

"""biochemical attenuation thresholds (doc 1)"""
# ref: hayes et al. (2015), chronobiology international
ftc_deficit_threshold = 0.30
rho_hormonal_penalty = 0.75

# ref: sim et al. (2019), european journal of applied physiology
ferritin_threshold = 35.0
rho_iron_penalty = 0.80

# ref: brancaccio et al. (2007), british medical bulletin
ck_threshold = 500.0
hscrp_threshold = 3.0
rho_muscle_penalty = 0.85

"""environmental friction coefficients (doc 1)"""
# ref: waterhouse et al. (2007), journal of sports sciences
k_tz_east = 0.02
k_tz_west = 0.015
k_alt = 0.00005
altitude_threshold = 1500.0

"""travel degradation index coefficients (doc 2 — updated)"""
# ref: muhm et al. (2007), nejm — spo2 in-flight telemetry
alpha_spo2 = 1.5

# ref: zalesin et al. (2001), annals of internal medicine
beta_immobility = 0.1

# ref: pmc10520441 — long haul travel and sleep
gamma_circadian_east = 1.5
gamma_circadian_west = 0.5

# legacy constants (preserved for backward compatibility)
alpha_hypoxic = 0.40
sea_level_pressure = 101325.0
cabin_pressure_default = 75000.0
beta_kinematic = 0.015
venous_stasis_no_compression = 1.5
venous_stasis_with_compression = 0.6

"""dynamic homeostatic stabilization thresholds (doc 2 — updated)"""
# ref: pmc7137984 — medical issues with commercial flights
# ref: waterhouse et al. (2005), journal of sports sciences
dhs_venous_sitting_max_minutes = 90
dhs_rmssd_deviation_threshold = 1.5
dhs_spo2_critical = 92.0
dhs_circadian_advance_per_day = 1.0

"""thermoregulatory model weights (doc 3 — updated)"""
# ref: buller et al. (2013), physiological measurement
# ref: gagnon et al. (2013), journal of applied physiology
w_thermal = 0.45
w_fluid = 0.30
w_metabolic = 0.25

# core temp estimation constants
# ref: buller et al. (2013) — extended kalman filter approach
core_temp_baseline = 37.0
core_temp_ceiling = 39.5
core_temp_alpha = 0.01

# ewbgt thresholds
ewbgt_precool_threshold = 26.0

# wearable fluid loss model (replaces scale-based bml)
# ref: gagnon et al. (2013), journal of applied physiology
k_dehydration = 0.000002
fluid_energy_trigger_kcal = 800
fluid_hr_zone_trigger_minutes = 30

# legacy fluid thresholds (preserved for backward compatibility)
bml_alert_threshold = 1.5
bml_critical_threshold = 3.0

# acclimation half-life in days
acclimation_half_days = 5.0
acclimation_full_days = 14.0

# clothing factor defaults
clothing_factor_default = 0.5

"""circadian / zeitgeber coefficients (doc 4 — updated to wmzia)"""
# ref: wright et al. (2013), current biology — gps light-dark cycle
kappa_light = 0.60

# ref: youngstedt et al. (2019), journal of physiology — exercise prc
kappa_exercise = 0.40

# exercise prc wearable thresholds
# ref: youngstedt et al. (2019)
exercise_prc_min_duration_minutes = 45
exercise_prc_min_strain = 14.0
exercise_prc_min_zone45_minutes = 20

# ref: zeitzer et al. (2000) — light sensitivity thresholds
light_half_max_lux = 120.0
light_max_lux = 10000.0
dark_threshold_lux = 10.0
blue_wavelength_peak = 460.0

# internal desynchrony penalty threshold
# ref: dijk & czeisler (1995), journal of neuroscience
idp_threshold_hours = 2.0
rem_drop_threshold_percent = 30.0
sleep_efficiency_desync_threshold = 80.0

# max phase shift per day (hours)
max_phase_shift_per_day = 1.5

# legacy zeitgeber coefficients (preserved for backward compatibility)
kappa_melatonin = 0.25
kappa_feeding = 0.10
melatonin_default_dose_mg = 0.5

"""bloodwork kinetics constants"""

# rbc kinetics
# ref: wada standard — rbc lifespan
rbc_lifespan_days = 120
rbc_normal_count = 5.0
epo_normal = 10.0
rbc_production_rate = 0.008

# iron kinetics
# ref: sim et al. (2019) — iron review
iron_half_life_days = 30.0
ferritin_steady_state = 100.0
iron_absorption_fraction = 0.10

# hormone kinetics (hill equation)
# ref: hayes et al. (2015) — cortisol/testosterone
max_secretion_rate = 20.0
threshold_kd = 50.0
hill_coefficient = 2.0
clearance_rate = 0.05

# nutrient kinetics (michaelis-menten)
default_vmax = 100.0
default_km = 50.0

# inflammation kinetics (bateman function)
# ref: brancaccio et al. (2007) — ck as marker
ck_appearance_rate = 0.15
ck_elimination_rate = 0.05
ck_volume_distribution = 10.0

# metabolic kinetics (bergman minimal model)
basal_glucose = 90.0
independent_clearance_p1 = 0.03
insulin_sensitivity_p3 = 0.0001

"""javelin biomechanics — elite male ceilings"""

# ref: bartonietz (2000) — javelin throwing: an approach to performance development
max_squat_kg = 190.0
max_pullover_kg = 110.0

# ref: pmc10690512 (2023) — hang power clean expertise; 1.64x bw for 80kg athlete
max_hang_clean_kg = 128.8

# ref: hubbard et al. — release parameter contributions to new-rules javelin
max_release_velocity_ms = 31.5
target_release_angle_deg = 36.0
target_attack_angle_deg = 2.0

# ref: makino et al. (2023) — kinematic contribution at different run-up velocities
target_runup_velocity_ms = 7.6

# ref: pmc10516106 (2023) — thorax-to-humerus energy transfer
baseline_energy_transfer_wkg = 35.0

# ref: ijisrt (2025) — plyometric training and javelin throw ability
plyo_contacts_base = 120
plyo_contacts_strength = 80
plyo_contacts_taper = 40

# periodization intensity modifiers
intensity_mod_hypertrophy = 0.80
intensity_mod_strength = 0.90
intensity_mod_peaking = 0.98
velocity_mod_hypertrophy = 0.85
velocity_mod_strength = 0.92
velocity_mod_peaking = 1.0

"""biomechanicals — autonomic & neural sequencing predictor (ansp)"""
# ref: frontiers in sports and active living (2025) — hrv mapping
# ref: journal of sports medicine (2012) — sleep deprivation and reaction time
# ref: walker et al. — rem and motor sequence consolidation

ansp_hrv_weight = 0.30
ansp_sleep_weight = 0.25
ansp_cortisol_weight = 0.25
ansp_magnesium_weight = 0.20

ansp_rem_optimal_percent = 22.0
ansp_rem_critical_percent = 15.0
ansp_magnesium_optimal_mg_dl = 2.0
ansp_magnesium_critical_mg_dl = 1.5

ansp_baseline_lag_ms = 0.0
ansp_max_lag_ms = 40.0
ansp_lag_hrv_coefficient = 8.0
ansp_lag_sleep_coefficient = 6.0
ansp_lag_cortisol_coefficient = 5.0
ansp_lag_magnesium_coefficient = 4.0

"""biomechanicals — dynamic biomechanical constraint regressor"""
# ref: stecco et al. (2013), journal of anatomy — hyaluronan and fascia
# ref: dattilo et al. (2011), medical hypotheses — sws and gh
# ref: abate et al. (2013), frontiers in endocrinology — ages and tendon
# ref: teng et al. (2021), journal of cellular physiology — zinc and ecm

constraint_deep_sleep_optimal_percent = 20.0
constraint_deep_sleep_critical_percent = 12.0
constraint_glucose_optimal_mg_dl = 100.0
constraint_glucose_age_threshold_mg_dl = 120.0
constraint_zinc_optimal_ug_dl = 80.0
constraint_zinc_critical_ug_dl = 60.0
constraint_b12_optimal_pg_ml = 400.0
constraint_b12_critical_pg_ml = 250.0

constraint_baseline_rom_deg = 160.0
constraint_max_rom_loss_deg = 20.0
constraint_temp_weight = 0.25
constraint_sleep_weight = 0.25
constraint_glucose_weight = 0.25
constraint_zinc_weight = 0.15
constraint_b12_weight = 0.10

"""biomechanicals — endocrine-architecture power profiler"""
# ref: crewther et al. (2011), sports medicine — steroid hormones
# ref: leproult & van cauter (2011), jama — sleep and testosterone
# ref: urhausen et al. (1995), sports medicine — ft:c ratio

power_ftc_weight = 0.35
power_insulin_weight = 0.20
power_hr_zone_weight = 0.25
power_sleep_weight = 0.20

power_ftc_catabolic_drop_percent = 30.0
power_insulin_low_threshold = 3.0
power_insulin_optimal = 8.0
power_hr_zone45_overload_minutes = 60
power_sleep_efficiency_floor = 75.0

power_baseline_rfd_percent = 100.0
power_max_rfd_drop_percent = 40.0

"""biomechanicals — pinn for dynamic tissue tolerance"""
# ref: baumert et al. (2019), frontiers in physiology — ck and crp
# ref: ogan & pritchett (2013), sports health — vitamin d
# ref: mah et al. (2011), sleep — sleep and performance

tissue_ck_weight = 0.30
tissue_crp_weight = 0.20
tissue_vitd_weight = 0.20
tissue_sleep_weight = 0.15
tissue_strain_weight = 0.15

tissue_ck_safe = 200.0
tissue_ck_danger = 800.0
tissue_crp_safe = 1.0
tissue_crp_danger = 5.0
tissue_vitd_optimal = 40.0
tissue_vitd_critical = 20.0
tissue_strain_safe = 10.0
tissue_strain_danger = 20.0

tissue_baseline_vmax_ms = 7.6
tissue_min_vmax_ms = 5.0

# physics constraints (impulse-momentum, hooke spring model)
tissue_athlete_mass_kg = 82.0
tissue_spring_k_optimal = 15000.0
tissue_decel_distance_m = 1.8

"""biomechanicals — systemic delivery & technique degradation simulator"""
# ref: noakes (2012), sports medicine — central governor model
# ref: amann & calbet (2008), journal of applied physiology — o2 transport
# ref: peeling et al. (2008) — iron and exercise performance
# ref: mairbäurl (2013), frontiers in physiology — rbc in sport

fatigue_ferritin_weight = 0.20
fatigue_rbc_weight = 0.20
fatigue_hba1c_weight = 0.15
fatigue_spo2_weight = 0.20
fatigue_cardio_weight = 0.25

fatigue_ferritin_optimal = 80.0
fatigue_ferritin_critical = 20.0
fatigue_rbc_low = 4.5
fatigue_rbc_high = 5.5
fatigue_epo_elevated = 20.0
fatigue_hba1c_optimal = 5.5
fatigue_hba1c_impaired = 6.5
fatigue_spo2_optimal = 97.0
fatigue_spo2_critical = 92.0
fatigue_rhr_elevated_bpm = 65
fatigue_rr_elevated = 18.0

fatigue_baseline_reps = 12
fatigue_min_reps = 3

"""gemini api configuration"""
import os
gemini_model_name = "gemini-2.5-flash"
gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
