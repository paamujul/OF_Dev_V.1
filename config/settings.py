"""
global constants and coefficients for the athlete wellness pipeline.
sources: project plan docs 1-4.
"""

import os

# ---------------------------------------------------------------------------
# hrv / wearable windows
# ---------------------------------------------------------------------------
# ref: plews et al. (2013), sports medicine
hrv_long_window = 28
hrv_short_window = 7
min_readings_req = 3

# wearable baseline weights (doc 1)
w_ans = 0.60
w_slp = 0.40

# ---------------------------------------------------------------------------
# autonomic readiness thresholds (doc 1)
# ---------------------------------------------------------------------------
# ref: buchheit (2014), frontiers in physiology
z_hrv_optimal_low = -0.5
z_hrv_optimal_high = 0.5
z_hrv_hyperactivity = 1.0
ans_penalty_per_z = 20
ans_hyperactivity_cap = 80

# ---------------------------------------------------------------------------
# sleep readiness thresholds (doc 1)
# ---------------------------------------------------------------------------
# ref: fullagar et al. (2015), sports medicine
sleep_efficiency_target = 85.0
total_sleep_time_target = 7.5
sleep_tst_cap = 8.0

# ---------------------------------------------------------------------------
# biochemical attenuation thresholds (doc 1)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# environmental friction coefficients (doc 1)
# ---------------------------------------------------------------------------
# ref: waterhouse et al. (2007), journal of sports sciences
k_tz_east = 0.02
k_tz_west = 0.015
k_alt = 0.00005
altitude_threshold = 1500.0

# ---------------------------------------------------------------------------
# travel degradation index coefficients (doc 2)
# ---------------------------------------------------------------------------
# ref: pmc8279034 — managing travel fatigue consensus statement
alpha_hypoxic = 0.40
sea_level_pressure = 101325.0
cabin_pressure_default = 75000.0

# ref: pmc10362518 — compression garments and venous return
beta_kinematic = 0.015
venous_stasis_no_compression = 1.5
venous_stasis_with_compression = 0.6

# ref: pmc10520441 — long haul travel and sleep
gamma_circadian_east = 1.5
gamma_circadian_west = 0.5

# ---------------------------------------------------------------------------
# dynamic homeostatic stabilization thresholds (doc 2)
# ---------------------------------------------------------------------------
# ref: pmc7137984 — medical issues with commercial flights
dhs_venous_sitting_max_minutes = 90
dhs_rmssd_deviation_threshold = 1.5
dhs_spo2_critical = 90.0

# ---------------------------------------------------------------------------
# thermoregulatory model weights (doc 3)
# ---------------------------------------------------------------------------
# ref: buller et al. (2013), physiological measurement
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

# fluid loss thresholds
# ref: duking et al. (2016), frontiers in physiology, pmc4754445
bml_alert_threshold = 1.5
bml_critical_threshold = 3.0

# acclimation half-life in days
acclimation_half_days = 5.0
acclimation_full_days = 14.0

# clothing factor defaults
clothing_factor_default = 0.5

# ---------------------------------------------------------------------------
# circadian / zeitgeber coefficients (doc 4)
# ---------------------------------------------------------------------------
# ref: khalsa et al. (2003), journal of physiology
kappa_light = 0.50

# ref: burgess et al. (2010), journal of clinical sleep medicine
kappa_melatonin = 0.25

# ref: youngstedt et al. (2019), journal of physiology
kappa_exercise = 0.15

# feeding coefficient (implicit from wehrens et al. 2017)
kappa_feeding = 0.10

# ref: zeitzer et al. (2000) — light sensitivity thresholds
light_half_max_lux = 120.0
light_max_lux = 10000.0
dark_threshold_lux = 10.0
blue_wavelength_peak = 460.0

# melatonin default dose
melatonin_default_dose_mg = 0.5

# internal desynchrony penalty threshold
idp_threshold_hours = 2.0

# max phase shift per day (hours)
max_phase_shift_per_day = 1.5

# ---------------------------------------------------------------------------
# bloodwork kinetics constants
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# gemini ai configuration
# ---------------------------------------------------------------------------
gemini_model_name = "gemini-2.5-flash"
gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

# ---------------------------------------------------------------------------
# javelin biomechanics — elite male ceilings
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# biomechanics algorithms — temporal sequencing (algo 1)
# ---------------------------------------------------------------------------
# ref: hirashima et al. (2002) — sequential muscle activation
optimal_interfire_delay_ms = 80.0
interfire_tolerance_ms = 15.0
energy_leakage_warning_threshold = 0.25

# ---------------------------------------------------------------------------
# biomechanics algorithms — block mechanics pinn (algo 2)
# ---------------------------------------------------------------------------
# ref: murakami et al. (2017) — front leg block kinetics
max_tolerable_grf_bw_baseline = 3.5
max_tolerable_grf_bw_ceiling = 6.5
block_deceleration_time_min = 0.08
block_deceleration_time_max = 0.20

# ---------------------------------------------------------------------------
# biomechanics algorithms — lever aerodynamic (algo 3)
# ---------------------------------------------------------------------------
# ref: hubbard & alaways (1987) — javelin flight mechanics
min_release_angle_deg = 32.0
max_release_angle_deg = 40.0
min_attack_angle_deg = -2.0
max_attack_angle_deg = 6.0

# ---------------------------------------------------------------------------
# biomechanics algorithms — power profiler (algo 4)
# ---------------------------------------------------------------------------
# ref: blazevich et al. (2006) — fascicle behavior
rfd_threshold_crossover = 250.0
min_fascicle_length_vl_cm = 8.5
min_type_ii_pct_for_rfd = 55.0
max_pennation_for_velocity = 25.0

# ---------------------------------------------------------------------------
# biomechanics algorithms — technique degradation (algo 5)
# ---------------------------------------------------------------------------
# ref: nybo & nielsen (2001) — hyperthermia and cns fatigue
degradation_heat_index_baseline = 25.0
degradation_heat_index_ceiling = 55.0
degradation_mcmc_simulations = 500
degradation_throws_per_session = 12
