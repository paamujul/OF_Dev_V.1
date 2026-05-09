"""
muscle architecture data generator.
produces scalar ultrasound and biopsy-proxy measurements for biomechanical algorithms.
"""

import os
import json


def generate():
    """produces muscle architecture data for an elite male javelin thrower."""
    output = {
        "assessment_date": "2026-04-10",
        "vastus_lateralis": {
            "fascicle_length_cm": 9.8,
            "pennation_angle_deg": 18.5,
            "muscle_thickness_cm": 3.2,
            "muscle_csa_cm2": 82.0,
            "type_ii_pct_csa": 62.0
        },
        "pectoralis_major": {
            "fascicle_length_cm": 14.2,
            "pennation_angle_deg": 12.0,
            "muscle_thickness_cm": 2.8,
            "muscle_csa_cm2": 58.0,
            "type_ii_pct_csa": 55.0
        },
        "gastrocnemius_medial": {
            "fascicle_length_cm": 5.6,
            "pennation_angle_deg": 22.0,
            "muscle_thickness_cm": 2.1,
            "muscle_csa_cm2": 45.0,
            "type_ii_pct_csa": 50.0
        }
    }

    base = os.path.dirname(os.path.abspath(__file__))
    outpath = os.path.normpath(os.path.join(base, "..", "mock", "muscle_architecture.json"))

    with open(outpath, "w") as f:
        json.dump(output, f, indent=4)

    print(f"generated muscle architecture data into '{outpath}'")
    return output


if __name__ == "__main__":
    generate()
