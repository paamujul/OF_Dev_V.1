"""
emg session data generator for javelin throw biomechanics.
simulates dual-channel emg at 1ms resolution for a ~500ms throw window.
channels: vastus_lateralis (lower body drive), pectoralis_major (upper body delivery).
"""

import os
import json
import numpy as np


def build_emg_burst(rng, onset_ms, duration_ms, peak_mv, window_ms):
    """generates a single emg burst envelope for a muscle channel."""
    signal = np.zeros(window_ms)
    end_ms = min(onset_ms + duration_ms, window_ms)
    t = np.arange(0, end_ms - onset_ms)
    rise = duration_ms * 0.3
    fall = duration_ms * 0.7

    for i, ti in enumerate(t):
        if ti < rise:
            envelope = peak_mv * (ti / rise)
        else:
            envelope = peak_mv * np.exp(-((ti - rise) / fall))
        noise = rng.normal(0, peak_mv * 0.08)
        signal[onset_ms + i] = max(0.0, envelope + noise)

    return signal


def build_session(rng, session_index, total_sessions):
    """generates one throw session with emg for both channels."""
    window_ms = 500
    progression = session_index / max(total_sessions - 1, 1)

    vl_onset = int(rng.normal(40, 5))
    vl_onset = max(20, min(80, vl_onset))
    vl_duration = int(rng.normal(140, 10))
    vl_peak = float(rng.normal(0.85 + progression * 0.15, 0.05))

    interfire_delay = int(rng.normal(95 - progression * 15, 8))
    interfire_delay = max(40, min(150, interfire_delay))

    pm_onset = vl_onset + interfire_delay
    pm_duration = int(rng.normal(120, 10))
    pm_peak = float(rng.normal(0.70 + progression * 0.20, 0.06))

    vl_signal = build_emg_burst(rng, vl_onset, vl_duration, vl_peak, window_ms)
    pm_signal = build_emg_burst(rng, pm_onset, pm_duration, pm_peak, window_ms)

    return {
        "window_ms": window_ms,
        "sample_rate_hz": 1000,
        "vastus_lateralis": {
            "onset_ms": vl_onset,
            "peak_amplitude_mv": round(vl_peak, 4),
            "duration_ms": vl_duration,
            "signal_mv": [round(float(v), 4) for v in vl_signal]
        },
        "pectoralis_major": {
            "onset_ms": pm_onset,
            "peak_amplitude_mv": round(pm_peak, 4),
            "duration_ms": pm_duration,
            "signal_mv": [round(float(v), 4) for v in pm_signal]
        },
        "interfire_delay_ms": interfire_delay
    }


def generate(num_sessions=24, seed=42):
    """produces emg session data across a training block."""
    rng = np.random.default_rng(seed)
    sessions = []

    for i in range(num_sessions):
        session = build_session(rng, i, num_sessions)
        session["session_index"] = i
        sessions.append(session)

    output = {
        "metadata": {
            "channels": ["vastus_lateralis", "pectoralis_major"],
            "window_ms": 500,
            "sample_rate_hz": 1000,
            "total_sessions": num_sessions,
            "seed": seed
        },
        "sessions": sessions
    }

    base = os.path.dirname(os.path.abspath(__file__))
    outpath = os.path.normpath(os.path.join(base, "..", "mock", "emg_session_data.json"))

    with open(outpath, "w") as f:
        json.dump(output, f, indent=4)

    print(f"generated emg session data into '{outpath}'")
    return output


if __name__ == "__main__":
    generate()
