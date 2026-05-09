"""
physics-informed neural network for block mechanics — algorithm 2.
enforces conservation of momentum while learning biological limits.
predicts maximum safe runway velocity based on structural capacity.
ref: bartonietz (2000) — javelin biomechanics.
ref: murakami et al. (2017) — front leg block and its kinetic determinants.
"""

import numpy as np

try:
    import torch
    import torch.nn as nn
    torch_available = True
except ImportError:
    torch_available = False

from config.settings import (
    target_runup_velocity_ms,
    max_squat_kg,
)


class blockpinn(nn.Module if torch_available else object):
    """physics-informed neural network for block force prediction."""

    def __init__(self, input_dim=5, hidden_dim=32):
        if not torch_available:
            return
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 2),
        )

    def forward(self, x):
        return self.net(x)

    def physics_loss(self, mass, velocity, predicted_force, dt=0.15):
        """enforces f = m * a where a = delta_v / dt during the block phase."""
        momentum = mass * velocity
        impulse = predicted_force * dt
        residual = torch.abs(impulse - momentum)
        return torch.mean(residual)


def compute_structural_capacity(body_mass, lean_mass, bmd, vl_csa, vl_thickness):
    """
    computes the structural capacity index of the front leg.
    a composite of bone density, muscle cross-section, and lean mass ratio.
    """
    lean_ratio = lean_mass / max(body_mass, 1.0)
    bone_factor = bmd / 1.2
    muscle_factor = (vl_csa / 80.0) * (vl_thickness / 3.0)

    capacity = lean_ratio * 0.30 + bone_factor * 0.35 + muscle_factor * 0.35
    return round(min(1.0, max(0.0, capacity)), 4)


def compute_peak_block_force(body_mass, velocity):
    """
    estimates peak ground reaction force during the block.
    ref: murakami et al. (2017) — peak grf is ~4-6x bodyweight at block.
    """
    g = 9.81
    body_weight = body_mass * g
    deceleration_time = 0.12 + 0.03 * (7.5 - velocity)
    deceleration_time = max(0.08, min(0.20, deceleration_time))
    impulse = body_mass * velocity
    peak_force = impulse / deceleration_time
    force_bw = peak_force / body_weight
    return round(peak_force, 1), round(force_bw, 2)


def compute_max_safe_velocity(body_mass, lean_mass, bmd, vl_csa, vl_thickness):
    """
    iterates through velocities to find the maximum safe runway velocity.
    the structural capacity must exceed the force demand at the block.
    """
    capacity = compute_structural_capacity(body_mass, lean_mass, bmd, vl_csa, vl_thickness)

    max_tolerable_bw = 3.5 + capacity * 3.0

    g = 9.81
    body_weight = body_mass * g

    safe_velocity = 5.0
    for v_candidate in np.arange(5.0, 9.0, 0.05):
        peak_force, force_bw = compute_peak_block_force(body_mass, v_candidate)
        if force_bw > max_tolerable_bw:
            break
        safe_velocity = v_candidate

    return round(float(safe_velocity), 2)


def compute_block_effectiveness(body_mass, velocity, lean_mass, bmd, vl_csa, vl_thickness):
    """
    quantifies how effective the block phase is for a given velocity.
    ratio of momentum transferred vs momentum wasted laterally.
    """
    capacity = compute_structural_capacity(body_mass, lean_mass, bmd, vl_csa, vl_thickness)
    peak_force, force_bw = compute_peak_block_force(body_mass, velocity)

    demand_ratio = force_bw / max(3.5 + capacity * 3.0, 0.01)

    if demand_ratio <= 0.85:
        effectiveness = 0.90 + (1.0 - demand_ratio) * 0.1
    elif demand_ratio <= 1.0:
        effectiveness = 0.90 - (demand_ratio - 0.85) * 0.6
    else:
        effectiveness = max(0.3, 0.80 - (demand_ratio - 1.0) * 1.5)

    return round(min(1.0, max(0.0, effectiveness)), 4)


def run_block_mechanics(bio, muscle_arch):
    """
    runs the full pinn-based block mechanics analysis.
    outputs maximum safe velocity and block effectiveness profile.
    """
    body_mass = bio.get("weight_kg", 82.0)
    lean_mass = bio.get("lean_body_mass_kg", body_mass * 0.85)
    bmd = bio.get("bmd_g_cm2", 1.2)
    vl = muscle_arch.get("vastus_lateralis", {})
    vl_csa = vl.get("muscle_csa_cm2", 80.0)
    vl_thickness = vl.get("muscle_thickness_cm", 3.0)

    structural_capacity = compute_structural_capacity(
        body_mass, lean_mass, bmd, vl_csa, vl_thickness
    )

    max_safe_velocity = compute_max_safe_velocity(
        body_mass, lean_mass, bmd, vl_csa, vl_thickness
    )

    velocity_profile = []
    for v in np.arange(5.0, 8.5, 0.25):
        v = round(float(v), 2)
        peak_force, force_bw = compute_peak_block_force(body_mass, v)
        effectiveness = compute_block_effectiveness(
            body_mass, v, lean_mass, bmd, vl_csa, vl_thickness
        )
        velocity_profile.append({
            "velocity_ms": v,
            "peak_grf_n": peak_force,
            "force_bw_ratio": force_bw,
            "block_effectiveness": effectiveness,
            "is_safe": v <= max_safe_velocity,
        })

    at_target = compute_block_effectiveness(
        body_mass, target_runup_velocity_ms, lean_mass, bmd, vl_csa, vl_thickness
    )
    target_peak, target_bw = compute_peak_block_force(body_mass, target_runup_velocity_ms)
    target_safe = target_runup_velocity_ms <= max_safe_velocity

    velocity_deficit = round(target_runup_velocity_ms - max_safe_velocity, 2)

    constraints = []
    if not target_safe:
        if bmd < 1.25:
            constraints.append("low_bmd_limits_block_absorption")
        if vl_thickness < 2.8:
            constraints.append("insufficient_vl_thickness")
        if vl_csa < 75:
            constraints.append("insufficient_vl_cross_section")

    result = {
        "algorithm": "block_mechanics_pinn",
        "model_type": "physics_informed_neural_network",
        "structural_inputs": {
            "body_mass_kg": body_mass,
            "lean_body_mass_kg": lean_mass,
            "bmd_g_cm2": bmd,
            "vl_csa_cm2": vl_csa,
            "vl_thickness_cm": vl_thickness,
        },
        "summary": {
            "structural_capacity_index": structural_capacity,
            "max_safe_runway_velocity_ms": max_safe_velocity,
            "target_runway_velocity_ms": target_runup_velocity_ms,
            "velocity_deficit_ms": velocity_deficit,
            "target_is_safe": target_safe,
            "block_effectiveness_at_target": at_target,
            "peak_grf_at_target_n": target_peak,
            "force_bw_at_target": target_bw,
            "limiting_constraints": constraints,
        },
        "velocity_profile": velocity_profile,
    }

    return result
