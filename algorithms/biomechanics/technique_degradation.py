"""
environmental readiness & technique degradation simulator — algorithm 5.
predicts which technique elements fail first under environmental stress.
uses hidden markov model to simulate state transitions from optimal to fatigued.
ref: nybo & nielsen (2001) — hyperthermia and central fatigue.
ref: gonzalez-alonso et al. (1999) — dehydration and cardiovascular drift.
"""

import numpy as np

from config.settings import (
    core_temp_baseline,
    core_temp_ceiling,
    bml_alert_threshold,
    bml_critical_threshold,
    target_release_angle_deg,
)


def build_transition_matrix(body_mass, body_fat, baseline_emg, env_temp, env_humidity):
    """
    builds the hmm transition probability matrix between technique states.
    states: optimal, mild_degradation, significant_degradation, failure.
    higher mass and heat stress increase transition probability to worse states.
    """
    heat_index = env_temp * 0.7 + env_humidity * 0.3
    heat_stress = min(1.0, max(0.0, (heat_index - 25.0) / 30.0))

    mass_factor = min(1.0, body_mass / 100.0)
    fat_factor = min(1.0, body_fat / 25.0)
    emg_resilience = min(1.0, baseline_emg / 1.0)

    fatigue_susceptibility = (
        heat_stress * 0.40
        + mass_factor * 0.20
        + fat_factor * 0.20
        + (1.0 - emg_resilience) * 0.20
    )

    p_stay_optimal = max(0.3, 0.85 - fatigue_susceptibility * 0.5)
    p_optimal_to_mild = min(0.5, fatigue_susceptibility * 0.4)
    p_optimal_to_sig = min(0.15, fatigue_susceptibility * 0.1)
    p_optimal_to_fail = max(0.0, 1.0 - p_stay_optimal - p_optimal_to_mild - p_optimal_to_sig)

    p_stay_mild = max(0.3, 0.70 - fatigue_susceptibility * 0.3)
    p_mild_to_sig = min(0.5, fatigue_susceptibility * 0.35)
    p_mild_to_fail = max(0.0, 1.0 - p_stay_mild - p_mild_to_sig)

    p_stay_sig = max(0.4, 0.60 - fatigue_susceptibility * 0.2)
    p_sig_to_fail = max(0.0, 1.0 - p_stay_sig)

    transition = np.array([
        [p_stay_optimal, p_optimal_to_mild, p_optimal_to_sig, p_optimal_to_fail],
        [0.05, p_stay_mild, p_mild_to_sig, p_mild_to_fail],
        [0.0, 0.05, p_stay_sig, p_sig_to_fail],
        [0.0, 0.0, 0.05, 0.95],
    ])

    for i in range(4):
        transition[i] = transition[i] / transition[i].sum()

    return np.round(transition, 4)


def simulate_technique_states(transition_matrix, num_throws=12, num_simulations=500, seed=42):
    """
    runs mcmc simulation of technique state evolution over a session.
    returns probability distribution over states at each throw.
    """
    rng = np.random.default_rng(seed)
    states = ["optimal", "mild_degradation", "significant_degradation", "failure"]
    num_states = len(states)

    state_counts = np.zeros((num_throws, num_states))

    for sim in range(num_simulations):
        current = 0
        for throw in range(num_throws):
            state_counts[throw, current] += 1
            probs = transition_matrix[current]
            current = rng.choice(num_states, p=probs)

    state_probs = state_counts / num_simulations

    throw_results = []
    for throw in range(num_throws):
        throw_results.append({
            "throw_number": throw + 1,
            "optimal_prob": round(float(state_probs[throw, 0]), 4),
            "mild_degradation_prob": round(float(state_probs[throw, 1]), 4),
            "significant_degradation_prob": round(float(state_probs[throw, 2]), 4),
            "failure_prob": round(float(state_probs[throw, 3]), 4),
            "most_likely_state": states[int(np.argmax(state_probs[throw]))],
        })

    return throw_results


def predict_technique_failures(body_mass, body_fat, baseline_emg, env_temp, env_humidity):
    """
    predicts which specific technique element fails first under fatigue.
    elbow angle degrades before muscle activation sequence in heat.
    """
    heat_index = env_temp * 0.7 + env_humidity * 0.3

    elbow_vulnerability = (
        (body_mass / 100.0) * 0.25
        + (heat_index / 55.0) * 0.40
        + (1.0 - min(1.0, baseline_emg / 1.0)) * 0.35
    )

    sequence_vulnerability = (
        (heat_index / 55.0) * 0.50
        + (body_fat / 25.0) * 0.25
        + (1.0 - min(1.0, baseline_emg / 1.0)) * 0.25
    )

    elbow_vulnerability = round(min(1.0, elbow_vulnerability), 4)
    sequence_vulnerability = round(min(1.0, sequence_vulnerability), 4)

    if elbow_vulnerability > sequence_vulnerability:
        first_failure = "elbow_angle"
        failure_description = (
            "cns fatigue in high heat causes the throwing arm elbow angle "
            "to drop prematurely during the delivery phase, reducing release height "
            "and increasing drag on the javelin."
        )
    else:
        first_failure = "muscle_activation_sequence"
        failure_description = (
            "proximal-to-distal firing sequence breaks down under systemic fatigue, "
            "causing premature pectoralis activation and energy leakage at the block."
        )

    predicted_elbow_drop = round(max(0.0, (elbow_vulnerability - 0.3) * 15.0), 1)
    predicted_sequence_delay_increase = round(max(0.0, (sequence_vulnerability - 0.3) * 25.0), 1)

    return {
        "elbow_angle": {
            "vulnerability_score": elbow_vulnerability,
            "predicted_angle_drop_deg": predicted_elbow_drop,
            "affected_release_angle_deg": round(
                target_release_angle_deg - predicted_elbow_drop * 0.3, 1
            ),
        },
        "muscle_activation_sequence": {
            "vulnerability_score": sequence_vulnerability,
            "predicted_delay_increase_ms": predicted_sequence_delay_increase,
        },
        "first_failure_element": first_failure,
        "failure_description": failure_description,
    }


def compute_degradation_risk_score(throw_results, technique_failures):
    """computes the final technical degradation risk score (0-100)."""
    last_throw = throw_results[-1]
    degradation_prob = (
        last_throw["mild_degradation_prob"] * 0.3
        + last_throw["significant_degradation_prob"] * 0.6
        + last_throw["failure_prob"] * 1.0
    )

    max_vulnerability = max(
        technique_failures["elbow_angle"]["vulnerability_score"],
        technique_failures["muscle_activation_sequence"]["vulnerability_score"],
    )

    risk = degradation_prob * 0.60 + max_vulnerability * 0.40
    risk_score = round(risk * 100.0, 1)

    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "moderate"
    else:
        risk_level = "low"

    return risk_score, risk_level


def run_technique_degradation(bio, emg_data, travel):
    """
    runs the full environmental technique degradation simulation.
    outputs risk scores, state probabilities, and predicted failure elements.
    """
    body_mass = bio.get("weight_kg", 82.0)
    body_fat = bio.get("body_fat_percent", 14.0)

    sessions = emg_data.get("sessions", [])
    if sessions:
        vl_peaks = [s["vastus_lateralis"]["peak_amplitude_mv"] for s in sessions]
        baseline_emg = float(np.mean(vl_peaks))
    else:
        baseline_emg = 0.8

    dest = travel.get("destination", {})
    env_temp = dest.get("temp_c", 30.0)
    env_humidity = dest.get("humidity_percent", 50.0)

    transition_matrix = build_transition_matrix(
        body_mass, body_fat, baseline_emg, env_temp, env_humidity
    )

    throw_results = simulate_technique_states(transition_matrix)

    technique_failures = predict_technique_failures(
        body_mass, body_fat, baseline_emg, env_temp, env_humidity
    )

    risk_score, risk_level = compute_degradation_risk_score(throw_results, technique_failures)

    result = {
        "algorithm": "technique_degradation_simulator",
        "model_type": "hmm_mcmc_simulation",
        "environmental_context": {
            "destination_temp_c": env_temp,
            "destination_humidity_pct": env_humidity,
            "destination_city": dest.get("city", "unknown"),
        },
        "athlete_inputs": {
            "body_mass_kg": body_mass,
            "body_fat_pct": body_fat,
            "baseline_emg_amplitude_mv": round(baseline_emg, 4),
        },
        "summary": {
            "technical_degradation_risk_score": risk_score,
            "risk_level": risk_level,
            "first_technique_to_fail": technique_failures["first_failure_element"],
            "failure_description": technique_failures["failure_description"],
        },
        "technique_vulnerabilities": technique_failures,
        "throw_state_progression": throw_results,
        "transition_matrix": transition_matrix.tolist(),
    }

    return result
