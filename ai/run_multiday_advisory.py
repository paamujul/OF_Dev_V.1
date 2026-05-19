"""
multi-day advisory generator.
produces a complete day-by-day advisory plan from today
through competition day, accounting for pre-travel,
travel, adaptation, and competition phases.

usage:
  python -m ai.run_multiday_advisory
"""

import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from google.genai import types

from config.settings import gemini_api_key, gemini_model_name
from ai.paper_rag import load_or_build_findings
from ai.utils import load_master_output
from ai.scenario_builder import build_scenario
from ai.validator import validate_and_stamp


output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")


def build_multiday_prompt():
    """system prompt for the multi-day advisory generator."""
    return """you are the obeo fit research advisor generating a COMPLETE DAY-BY-DAY advisory plan for an elite athlete from today through competition day.

you have access to:
1. a master findings dictionary extracted via rag from peer-reviewed sports science research papers
2. the athlete's current biometric telemetry and algorithmic outputs
3. the full competition scenario (origin, destination, travel date, competition date)

GENERATE A JSON OBJECT with this EXACT structure:

{
  "plan_metadata": {
    "generated_at": "<ISO datetime>",
    "athlete_name": "<name>",
    "origin": "<city>",
    "destination": "<city>",
    "travel_date": "<date>",
    "competition_date": "<date>",
    "total_days": <int>,
    "days_to_competition": <int>
  },

  "executive_summary": "<3-4 sentence overview of the entire plan arc: what are the biggest risks, what is the strategy, what is the projected readiness at competition>",

  "daily_advisories": [
    {
      "date": "YYYY-MM-DD",
      "day_number": <int>,
      "days_to_competition": <int>,
      "phase": "<pre_travel_base|pre_travel_sharpening|pre_travel_taper|travel_day|adaptation|competition>",
      "phase_label": "<human readable phase name>",
      "location": "<city>",

      "day_summary": {
        "narrative": "<2-3 sentence summary of where the athlete stands this day and what the priority is>",
        "overall_readiness_score": <float>,
        "readiness_trend": "improving|stable|declining",
        "key_systems_status": {
          "autonomic": {"status": "optimal|suboptimal|compromised", "detail": "<brief>"},
          "sleep": {"status": "optimal|suboptimal|compromised", "detail": "<brief>"},
          "bloodwork": {"status": "optimal|suboptimal|compromised", "detail": "<brief>"},
          "musculoskeletal": {"status": "optimal|suboptimal|compromised", "detail": "<brief>"},
          "thermoregulatory": {"status": "optimal|suboptimal|compromised", "detail": "<brief>"},
          "circadian": {"status": "optimal|suboptimal|compromised", "detail": "<brief>"}
        }
      },

      "forward_trajectory": {
        "next_24h": "<what to expect and focus on in the next 24 hours>",
        "next_3_days": "<trajectory outlook for the next 3 days>",
        "competition_readiness_projection": "<projected readiness at competition if current protocols are followed from this day forward>"
      },

      "readiness_projection": {
        "estimated_score": <float>,
        "trend": "improving|stable|declining",
        "limiting_system": "<the system most holding back readiness today>"
      },

      "top_3_suggestions": [
        {
          "rank": 1,
          "suggestion_id": "<unique slug>",
          "title": "<short title>",
          "category": "<category>",
          "what_to_do": "<PRECISE: exact dosage, exact timing, exact duration>",
          "why": "<1 sentence rationale tied to data>",
          "expected_outcome": "<what changes and by when>",
          "source_finding_id": "<from master findings dictionary if applicable>",
          "data_trigger": "<the exact biomarker or metric that triggered this suggestion>",
          "data_trigger_value": "<the actual current or projected value>",
          "data_trigger_threshold": "<the threshold it crossed or is approaching>"
        },
        { "rank": 2, "..." : "..." },
        { "rank": 3, "..." : "..." }
      ],

      "nutrition_protocol": {
        "hydration_liters": <float>,
        "key_supplements": ["<supplement + dosage>"],
        "meal_timing_notes": "<any specific meal timing guidance>"
      },

      "training_guidance": {
        "intensity": "<rest|low|moderate|high|competition>",
        "session_type": "<description of what to do>",
        "duration_minutes": <int>,
        "timing": "<when to train>"
      },

      "sleep_protocol": {
        "target_bedtime": "<HH:MM>",
        "target_wake": "<HH:MM>",
        "target_hours": <float>,
        "environment_notes": "<room temp, light blocking, etc>"
      },

      "warnings": ["<any anti-interventions or things NOT to do today>"],

      "improvement_candidates": [
        {
          "suggestion_id": "<matches a suggestion_id from top_3_suggestions>",
          "reason_for_tracking": "<why this suggestion might produce notable improvement>",
          "measurable_outcome": "<what specific metric to watch to confirm improvement>"
        }
      ]
    }
  ],

  "biomarker_tracking": {
    "ferritin_projection": {
      "start_value": <float>,
      "target_value": <float>,
      "projected_competition_day_value": <float>,
      "intervention": "<what is being done>"
    },
    "circadian_projection": {
      "initial_wtmin": "<HH:MM>",
      "target_wtmin": "<HH:MM for destination>",
      "adaptation_strategy": "<summary>"
    },
    "thermoregulatory_projection": {
      "initial_power_percent": <float>,
      "target_power_percent": <float>,
      "acclimation_strategy": "<summary>"
    }
  }
}

RULES:
1. generate an entry for EVERY SINGLE DAY from start_date to competition_date (inclusive). do not skip days.
2. suggestions must be PRECISE: "take 325mg ferrous sulfate with 200mg vitamin c at 7:00am on empty stomach" not "consider iron"
3. all biomarker values must reference real data from the athlete state
4. the plan must show PROGRESSION: readiness should improve over time if protocols are followed
5. travel day must include in-flight protocols (mobilization, hydration, compression, circadian)
6. competition day must include pre-competition protocols (precooling, warm-up, nutrition timing)
7. account for the timezone shift between origin and destination
8. account for destination heat conditions and ewbgt
9. taper training volume appropriately in the final week
10. every suggestion MUST include data_trigger, data_trigger_value, and data_trigger_threshold fields
11. every day MUST include forward_trajectory with next_24h, next_3_days, and competition_readiness_projection
12. every day MUST include improvement_candidates for at least the most impactful suggestion
13. day_summary must be an object with narrative, overall_readiness_score, readiness_trend, and key_systems_status
14. return ONLY the json object. no markdown fences, no text before or after"""


def generate_multiday_advisory(origin_city="new delhi", destination_city="doha",
                                travel_date="2026-06-06", competition_date="2026-06-10",
                                start_date=None):
    """generates the full multi-day advisory plan."""
    if not gemini_api_key:
        print("error: no gemini api key found")
        print("  set GEMINI_API_KEY in your environment")
        sys.exit(1)

    if start_date is None:
        start_date = datetime.now().strftime("%Y-%m-%d")

    print("1. loading master findings from research papers...")
    master_findings = load_or_build_findings()
    finding_count = master_findings.get("total_findings", 0)
    print(f"  loaded {finding_count} findings")

    print("2. loading current athlete state...")
    master_output = load_master_output()
    readiness = master_output.get("master_readiness", {}).get("score", 0)
    print(f"  current readiness: {readiness}")

    print("3. building competition scenario...")
    scenario = build_scenario(origin_city, destination_city, travel_date, competition_date, start_date)
    print(f"  {scenario['origin']['city']} to {scenario['destination']['city']}")
    print(f"  distance: {scenario['distance_km']} km")
    print(f"  travel: {scenario['travel_date']} | competition: {scenario['competition_date']}")
    print(f"  timezone shift: {scenario['timezone_shift_hours']}h {scenario['direction']}")
    print(f"  destination heat: {scenario['destination']['avg_temp_celsius']}c / ewbgt {scenario['destination']['ewbgt_expected']}")
    print(f"  flight duration: {scenario['flight_duration_hours']}h")
    print(f"  phases: {len(scenario['phases'])}")

    total_days = (datetime.strptime(competition_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days + 1
    print(f"4. generating {total_days}-day advisory plan...")
    print("  (this will take 1-2 minutes)")

    client = genai.Client(api_key=gemini_api_key)

    slim_findings = {
        "total_findings": master_findings.get("total_findings", 0),
        "categories": {},
    }
    for cat, items in master_findings.get("categories", {}).items():
        slim_items = []
        for item in (items if isinstance(items, list) else [items]):
            slim_items.append({
                k: v for k, v in item.items()
                if k in ("finding_id", "finding", "actionable_recommendation",
                          "magnitude_of_effect", "evidence_level", "relevant_biomarkers",
                          "priority_rank", "category")
            })
        slim_findings["categories"][cat] = slim_items

    slim_state = {}
    for key in ("meta", "master_readiness", "risk_assessment", "system_scores",
                "bloodwork_kinetics", "travel_composite", "circadian_shift",
                "thermoregulatory", "fatigue_horizon", "sleep_composite",
                "ansp_readiness"):
        if key in master_output:
            slim_state[key] = master_output[key]

    context = json.dumps({
        "master_findings": slim_findings,
        "current_athlete_state": slim_state,
        "competition_scenario": scenario,
    }, indent=2, default=str)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=gemini_model_name,
                contents=(
                    f"generate the complete day-by-day advisory plan for this athlete "
                    f"from {start_date} through {competition_date} "
                    f"({total_days} entries total). use all available context.\n\n"
                    f"{context}"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=build_multiday_prompt(),
                    temperature=0.3,
                    max_output_tokens=65536,
                ),
            )
            break
        except Exception as e:
            wait = 30 * (attempt + 1)
            if attempt < max_retries - 1:
                print(f"  rate limited (attempt {attempt + 1}/{max_retries}), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  error: all {max_retries} attempts failed: {e}")
                sys.exit(1)

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]

    try:
        advisory = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"\n  warning: json parse issue: {e}")
        print("  attempting to salvage partial json...")
        last_brace = raw.rfind("}")
        if last_brace > 0:
            try:
                advisory = json.loads(raw[:last_brace + 1])
                print("  salvaged partial json successfully")
            except json.JSONDecodeError:
                advisory = {"raw_response": raw, "parse_error": str(e)}
        else:
            advisory = {"raw_response": raw, "parse_error": str(e)}

    day_count = len(advisory.get("daily_advisories", []))
    print(f"\n  generated {day_count} daily advisories")

    print("5. validating advisory against physiological constraints...")
    advisory, report = validate_and_stamp(advisory, master_findings)
    report.print_report()

    os.makedirs(output_dir, exist_ok=True)
    plan_path = os.path.join(output_dir, "multiday_advisory.json")
    with open(plan_path, "w") as f:
        json.dump(advisory, f, indent=2)
    print(f"  plan written to {plan_path}")

    if "executive_summary" in advisory:
        print(f"\n  executive summary:")
        print(f"  {advisory['executive_summary']}")

    if "daily_advisories" in advisory:
        print(f"\n  --- day-by-day top priorities ---")
        for day in advisory["daily_advisories"]:
            date = day.get("date", "?")
            phase = day.get("phase_label", day.get("phase", "?"))
            loc = day.get("location", "?")
            est = day.get("readiness_projection", {}).get("estimated_score", "?")
            dtc = day.get("days_to_competition", "?")
            top = day.get("top_3_suggestions", [{}])[0].get("title", "-") if day.get("top_3_suggestions") else "-"
            print(f"  {date} | d-{dtc} | {phase:28s} | {loc:10s} | readiness: {est:>5} | #1: {top}")

    return advisory


if __name__ == "__main__":
    generate_multiday_advisory(
        origin_city="new delhi",
        destination_city="doha",
        travel_date="2026-06-06",
        competition_date="2026-06-10",
    )

