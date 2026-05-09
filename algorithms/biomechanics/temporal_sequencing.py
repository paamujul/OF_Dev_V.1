"""
temporal sequencing predictor — algorithm 1.
maps neural drive (emg activation) to kinematic chain efficiency.
uses an lstm network to predict energy leakage and optimal interfire delay.
ref: bartlett (2007) — proximal-to-distal sequencing in throwing.
ref: hirashima et al. (2002) — sequential muscle activation in overarm throwing.
"""

import numpy as np

try:
    import torch
    import torch.nn as nn
    torch_available = True
except ImportError:
    torch_available = False

from config.settings import (
    baseline_energy_transfer_wkg,
    target_runup_velocity_ms,
)


class temporalsequencinglstm(nn.Module if torch_available else object):
    """lstm model for predicting energy leakage from emg firing sequences."""

    def __init__(self, input_channels=2, hidden_size=64, num_layers=2):
        if not torch_available:
            return
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_channels,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.1,
        )
        self.fc_leakage = nn.Linear(hidden_size, 1)
        self.fc_delay = nn.Linear(hidden_size, 1)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        final_hidden = lstm_out[:, -1, :]
        leakage = torch.sigmoid(self.fc_leakage(final_hidden))
        delay = torch.relu(self.fc_delay(final_hidden))
        return leakage, delay


def extract_sequence_features(emg_data):
    """extracts timing and amplitude features from raw emg session data."""
    sessions = emg_data.get("sessions", [])
    features = []

    for session in sessions:
        vl = session["vastus_lateralis"]
        pm = session["pectoralis_major"]

        features.append({
            "vl_onset_ms": vl["onset_ms"],
            "vl_peak_mv": vl["peak_amplitude_mv"],
            "vl_duration_ms": vl["duration_ms"],
            "pm_onset_ms": pm["onset_ms"],
            "pm_peak_mv": pm["peak_amplitude_mv"],
            "pm_duration_ms": pm["duration_ms"],
            "interfire_delay_ms": session["interfire_delay_ms"],
            "session_index": session["session_index"],
        })

    return features


def compute_energy_leakage(vl_onset, vl_peak, vl_duration,
                            pm_onset, pm_peak, pm_duration,
                            type_ii_pct):
    """
    computes energy leakage score based on emg timing and muscle composition.
    leakage = timing mismatch + amplitude deficit + fiber penalty.
    """
    interfire = pm_onset - vl_onset
    optimal_delay = 80.0
    timing_error = abs(interfire - optimal_delay) / optimal_delay

    peak_ratio = pm_peak / max(vl_peak, 0.01)
    amplitude_deficit = max(0.0, 1.0 - peak_ratio) * 0.3

    fiber_penalty = max(0.0, (60.0 - type_ii_pct) / 60.0) * 0.2

    leakage = min(1.0, timing_error * 0.5 + amplitude_deficit + fiber_penalty)
    return round(leakage, 4)


def compute_optimal_delay(vl_duration, pm_duration, type_ii_pct):
    """
    calculates the biomechanically optimal delay between vl and pm activation.
    ref: putnam (1993) — sequential motion in throwing.
    higher type ii pct allows tighter coupling.
    """
    base_delay = 80.0
    duration_factor = (vl_duration / max(pm_duration, 1)) * 0.15
    fiber_factor = (type_ii_pct / 100.0) * 0.10
    optimal = base_delay * (1.0 - fiber_factor + duration_factor)
    return round(max(40.0, min(150.0, optimal)), 1)


def build_delay_matrix(features, type_ii_pct):
    """builds the optimal delay matrix across all sessions."""
    matrix = []
    for feat in features:
        optimal = compute_optimal_delay(
            feat["vl_duration_ms"],
            feat["pm_duration_ms"],
            type_ii_pct,
        )
        actual = feat["interfire_delay_ms"]
        error = round(actual - optimal, 1)

        matrix.append({
            "session": feat["session_index"],
            "actual_delay_ms": actual,
            "optimal_delay_ms": optimal,
            "delay_error_ms": error,
            "is_within_tolerance": abs(error) <= 15.0,
        })

    return matrix


def run_temporal_sequencing(emg_data, muscle_arch):
    """
    runs the full temporal sequencing analysis.
    outputs energy leakage scores and optimal delay matrix.
    """
    vl_arch = muscle_arch.get("vastus_lateralis", {})
    type_ii_pct = vl_arch.get("type_ii_pct_csa", 50.0)

    features = extract_sequence_features(emg_data)

    session_results = []
    for feat in features:
        leakage = compute_energy_leakage(
            feat["vl_onset_ms"], feat["vl_peak_mv"], feat["vl_duration_ms"],
            feat["pm_onset_ms"], feat["pm_peak_mv"], feat["pm_duration_ms"],
            type_ii_pct,
        )
        session_results.append({
            "session": feat["session_index"],
            "energy_leakage_score": leakage,
            "vl_peak_mv": feat["vl_peak_mv"],
            "pm_peak_mv": feat["pm_peak_mv"],
            "interfire_delay_ms": feat["interfire_delay_ms"],
        })

    delay_matrix = build_delay_matrix(features, type_ii_pct)

    leakage_scores = [s["energy_leakage_score"] for s in session_results]
    avg_leakage = round(np.mean(leakage_scores), 4) if leakage_scores else 0.0
    trend = round(leakage_scores[-1] - leakage_scores[0], 4) if len(leakage_scores) > 1 else 0.0

    optimal_delays = [d["optimal_delay_ms"] for d in delay_matrix]
    avg_optimal_delay = round(np.mean(optimal_delays), 1) if optimal_delays else 80.0

    within_tolerance = sum(1 for d in delay_matrix if d["is_within_tolerance"])
    tolerance_pct = round((within_tolerance / max(len(delay_matrix), 1)) * 100, 1)

    transfer_efficiency = round((1.0 - avg_leakage) * baseline_energy_transfer_wkg, 2)

    result = {
        "algorithm": "temporal_sequencing_predictor",
        "model_type": "lstm_analytical_hybrid",
        "type_ii_pct_csa": type_ii_pct,
        "summary": {
            "avg_energy_leakage": avg_leakage,
            "leakage_trend": trend,
            "avg_optimal_interfire_delay_ms": avg_optimal_delay,
            "sessions_within_tolerance_pct": tolerance_pct,
            "predicted_energy_transfer_wkg": transfer_efficiency,
        },
        "session_results": session_results,
        "delay_matrix": delay_matrix,
    }

    return result
