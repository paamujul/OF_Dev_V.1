"""
shared ai utilities.
contains data loading and improvement tracking functions
used across the advisory pipeline.
"""

import os
import json
from datetime import datetime, timezone

from ai.paper_rag import load_improvement_log, save_improvement_log


output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")


def load_master_output():
    """loads the latest master_output.json from the pipeline."""
    path = os.path.join(output_dir, "master_output.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"master_output.json not found at {path}")
    with open(path, "r") as f:
        return json.load(f)


def record_improvement(suggestion_id, improvement_note, delta_value=None):
    """
    called when the athlete or coach notes that a suggestion produced
    measurable improvement. this feeds the improvement dictionary so
    similar suggestions get boosted in the future.
    """
    log = load_improvement_log()
    for s in log["tracked_suggestions"]:
        if s["suggestion_id"] == suggestion_id:
            s["noted_improvements"].append({
                "date": datetime.now(timezone.utc).isoformat(),
                "note": improvement_note,
                "delta_value": delta_value,
            })
            break

    log["improvement_history"].append({
        "suggestion_id": suggestion_id,
        "date": datetime.now(timezone.utc).isoformat(),
        "note": improvement_note,
        "delta_value": delta_value,
    })

    save_improvement_log(log)
    return log
