"""
post-generation hallucination validator.
checks every ai-generated advisory against hard physiological
constraints, data grounding, citation validity, and dosage safety
ceilings before the output gets written to disk.

architecture:
  gemini output --> json parser --> validator --> approved output
                                       |
                                       v
                                 flagged issues
                                 (with reasons)
"""

import re
import json
from datetime import datetime


# =============================================================================
# physiological range constraints
# =============================================================================

PHYSIOLOGICAL_RANGES = {
    "readiness_score": {"min": 0, "max": 100},
    "ferritin_ng_ml": {"min": 5, "max": 300},
    "hemoglobin_g_dl": {"min": 7, "max": 20},
    "testosterone_ng_dl": {"min": 100, "max": 1500},
    "cortisol_ug_dl": {"min": 1, "max": 50},
    "crp_mg_l": {"min": 0, "max": 30},
    "tsh_miu_l": {"min": 0.1, "max": 15},
    "vitamin_d_ng_ml": {"min": 5, "max": 150},
    "iron_saturation_percent": {"min": 5, "max": 60},
    "sleep_hours": {"min": 3, "max": 14},
    "hydration_liters": {"min": 1, "max": 12},
    "training_duration_minutes": {"min": 0, "max": 360},
    "body_temp_celsius": {"min": 35, "max": 42},
    "heart_rate_bpm": {"min": 30, "max": 220},
    "hrv_rmssd_ms": {"min": 5, "max": 200},
    "spo2_percent": {"min": 80, "max": 100},
    "ewbgt": {"min": 10, "max": 45},
}


# =============================================================================
# dosage safety ceilings (daily maximums)
# =============================================================================

DOSAGE_LIMITS = {
    "ferrous sulfate": {"max_mg": 650, "unit": "mg"},
    "iron": {"max_mg": 100, "unit": "mg"},
    "vitamin c": {"max_mg": 2000, "unit": "mg"},
    "vitamin d": {"max_iu": 10000, "unit": "IU"},
    "magnesium": {"max_mg": 500, "unit": "mg"},
    "zinc": {"max_mg": 50, "unit": "mg"},
    "melatonin": {"max_mg": 10, "unit": "mg"},
    "caffeine": {"max_mg": 600, "unit": "mg"},
    "creatine": {"max_g": 20, "unit": "g"},
    "sodium bicarbonate": {"max_g": 30, "unit": "g"},
    "beetroot juice": {"max_ml": 500, "unit": "ml"},
    "omega 3": {"max_g": 5, "unit": "g"},
    "beta alanine": {"max_g": 10, "unit": "g"},
    "tart cherry": {"max_ml": 500, "unit": "ml"},
    "electrolyte": {"max_mg": 5000, "unit": "mg"},
    "sodium": {"max_mg": 5000, "unit": "mg"},
    "potassium": {"max_mg": 4700, "unit": "mg"},
}

# when checking a generic name, skip if a more specific compound is nearby.
# e.g. "325mg ferrous sulfate" should NOT also trigger the "iron" rule.
DOSAGE_EXCLUSIONS = {
    "iron": ["ferrous sulfate", "ferrous fumarate", "ferrous gluconate", "iron bisglycinate"],
    "sodium": ["sodium bicarbonate", "sodium citrate"],
}


# =============================================================================
# readiness consistency constraints
# =============================================================================

MAX_READINESS_JUMP_PER_DAY = 5.0
MAX_READINESS_DROP_PER_DAY = 15.0
MAX_READINESS_DROP_TRAVEL_DAY = 20.0


# =============================================================================
# validator result classes
# =============================================================================

class ValidationIssue:
    """represents a single validation problem."""

    SEVERITY_ERROR = "error"
    SEVERITY_WARNING = "warning"
    SEVERITY_INFO = "info"

    def __init__(self, severity, category, message, day=None, field=None, value=None):
        self.severity = severity
        self.category = category
        self.message = message
        self.day = day
        self.field = field
        self.value = value

    def to_dict(self):
        d = {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
        }
        if self.day is not None:
            d["day"] = self.day
        if self.field is not None:
            d["field"] = self.field
        if self.value is not None:
            d["value"] = self.value
        return d

    def __repr__(self):
        prefix = f"[day {self.day}] " if self.day else ""
        return f"[{self.severity.upper()}] {prefix}{self.category}: {self.message}"


class ValidationReport:
    """aggregates all validation issues for an advisory."""

    def __init__(self):
        self.issues = []
        self.days_checked = 0
        self.suggestions_checked = 0

    def add(self, issue):
        self.issues.append(issue)

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == ValidationIssue.SEVERITY_ERROR]

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == ValidationIssue.SEVERITY_WARNING]

    @property
    def infos(self):
        return [i for i in self.issues if i.severity == ValidationIssue.SEVERITY_INFO]

    @property
    def is_clean(self):
        return len(self.errors) == 0

    def summary(self):
        return {
            "days_checked": self.days_checked,
            "suggestions_checked": self.suggestions_checked,
            "total_issues": len(self.issues),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "info": len(self.infos),
            "passed": self.is_clean,
        }

    def to_dict(self):
        return {
            "validation_summary": self.summary(),
            "issues": [i.to_dict() for i in self.issues],
        }

    def print_report(self):
        s = self.summary()
        print(f"\n  validation report:")
        print(f"    days checked: {s['days_checked']}")
        print(f"    suggestions checked: {s['suggestions_checked']}")
        print(f"    errors: {s['errors']} | warnings: {s['warnings']} | info: {s['info']}")
        if self.is_clean:
            print("    result: PASSED")
        else:
            print("    result: FAILED")
            for issue in self.errors:
                print(f"      {issue}")
        for issue in self.warnings[:10]:
            print(f"      {issue}")


# =============================================================================
# individual validators
# =============================================================================

def validate_readiness_range(advisory, report):
    """checks that all readiness scores are within 0-100."""
    days = advisory.get("daily_advisories", [])
    for day in days:
        date = day.get("date", "?")

        score = day.get("readiness_projection", {}).get("estimated_score")
        if score is not None:
            if not (0 <= score <= 100):
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "range_validation",
                    f"readiness score {score} is outside valid range [0-100]",
                    day=date, field="readiness_projection.estimated_score", value=score,
                ))

        ds_score = day.get("day_summary", {}).get("overall_readiness_score")
        if ds_score is not None:
            if not (0 <= ds_score <= 100):
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "range_validation",
                    f"day_summary readiness {ds_score} is outside valid range [0-100]",
                    day=date, field="day_summary.overall_readiness_score", value=ds_score,
                ))


def validate_readiness_consistency(advisory, report):
    """checks that readiness doesn't jump unrealistically between days."""
    days = advisory.get("daily_advisories", [])
    prev_score = None

    for day in days:
        date = day.get("date", "?")
        score = day.get("readiness_projection", {}).get("estimated_score")

        if score is not None and prev_score is not None:
            delta = score - prev_score
            phase = day.get("phase", "")

            max_jump = MAX_READINESS_JUMP_PER_DAY
            max_drop = MAX_READINESS_DROP_TRAVEL_DAY if phase == "travel_day" else MAX_READINESS_DROP_PER_DAY

            if delta > max_jump:
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "consistency",
                    f"readiness jumped +{delta:.1f} in one day (max allowed: +{max_jump}). "
                    f"prev: {prev_score}, current: {score}",
                    day=date, field="readiness_projection.estimated_score", value=delta,
                ))
            elif delta < -max_drop:
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "consistency",
                    f"readiness dropped {delta:.1f} in one day (max allowed: -{max_drop}). "
                    f"prev: {prev_score}, current: {score}",
                    day=date, field="readiness_projection.estimated_score", value=delta,
                ))

        if score is not None:
            prev_score = score


def validate_sleep_protocol(advisory, report):
    """checks that sleep targets are physiologically reasonable."""
    days = advisory.get("daily_advisories", [])
    for day in days:
        date = day.get("date", "?")
        sleep = day.get("sleep_protocol", {})

        target_hours = sleep.get("target_hours")
        if target_hours is not None:
            rng = PHYSIOLOGICAL_RANGES["sleep_hours"]
            if not (rng["min"] <= target_hours <= rng["max"]):
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "range_validation",
                    f"sleep target {target_hours}h is outside valid range [{rng['min']}-{rng['max']}]",
                    day=date, field="sleep_protocol.target_hours", value=target_hours,
                ))


def validate_hydration(advisory, report):
    """checks that hydration targets are reasonable."""
    days = advisory.get("daily_advisories", [])
    for day in days:
        date = day.get("date", "?")
        nutrition = day.get("nutrition_protocol", {})

        liters = nutrition.get("hydration_liters")
        if liters is not None:
            rng = PHYSIOLOGICAL_RANGES["hydration_liters"]
            if not (rng["min"] <= liters <= rng["max"]):
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "range_validation",
                    f"hydration target {liters}L is outside valid range [{rng['min']}-{rng['max']}]",
                    day=date, field="nutrition_protocol.hydration_liters", value=liters,
                ))


def validate_training_duration(advisory, report):
    """checks that training durations are reasonable."""
    days = advisory.get("daily_advisories", [])
    for day in days:
        date = day.get("date", "?")
        training = day.get("training_guidance", {})

        duration = training.get("duration_minutes")
        if duration is not None:
            rng = PHYSIOLOGICAL_RANGES["training_duration_minutes"]
            if not (rng["min"] <= duration <= rng["max"]):
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "range_validation",
                    f"training duration {duration} min is outside valid range [{rng['min']}-{rng['max']}]",
                    day=date, field="training_guidance.duration_minutes", value=duration,
                ))


def _extract_dosage(text, supplement_name):
    """
    extracts a numeric dosage from a text string for a given supplement.
    returns (value, unit) or (None, None).
    """
    text_lower = text.lower()
    if supplement_name.lower() not in text_lower:
        return None, None

    patterns = [
        rf'(\d+(?:\.\d+)?)\s*mg\b',
        rf'(\d+(?:\.\d+)?)\s*g\b',
        rf'(\d+(?:\.\d+)?)\s*ml\b',
        rf'(\d+(?:\.\d+)?)\s*iu\b',
        rf'(\d+(?:\.\d+)?)\s*mcg\b',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            # find the match closest to the supplement name
            idx = text_lower.find(supplement_name.lower())
            best_val = None
            best_dist = float('inf')
            for m in re.finditer(pattern, text_lower):
                dist = abs(m.start() - idx)
                if dist < best_dist:
                    best_dist = dist
                    best_val = float(m.group(1))
                    unit_match = re.search(r'(mg|g|ml|iu|mcg)', m.group(0))
                    best_unit = unit_match.group(1) if unit_match else "mg"
            if best_val is not None:
                return best_val, best_unit

    return None, None


def validate_dosage_safety(advisory, report):
    """checks that all supplement dosages are within safe daily limits."""
    days = advisory.get("daily_advisories", [])

    for day in days:
        date = day.get("date", "?")
        report.suggestions_checked += len(day.get("top_3_suggestions", []))

        all_text = ""
        for suggestion in day.get("top_3_suggestions", []):
            all_text += " " + suggestion.get("what_to_do", "")
            all_text += " " + suggestion.get("title", "")

        supplements = day.get("nutrition_protocol", {}).get("key_supplements", [])
        for supp in supplements:
            all_text += " " + supp

        all_text_lower = all_text.lower()

        # check longer/more specific compound names first
        checked_compounds = set()

        for name, limits in sorted(DOSAGE_LIMITS.items(), key=lambda x: -len(x[0])):
            if name.lower() not in all_text_lower:
                continue

            # skip generic names when a specific compound was already checked
            exclusions = DOSAGE_EXCLUSIONS.get(name, [])
            skip = False
            for exc in exclusions:
                if exc.lower() in all_text_lower:
                    skip = True
                    break
            if skip:
                continue

            value, unit = _extract_dosage(all_text, name)
            if value is None:
                continue

            checked_compounds.add(name)

            if "max_mg" in limits:
                limit_val = limits["max_mg"]
                if unit == "g":
                    value *= 1000
                    unit = "mg"
                if unit == "mg" and value > limit_val:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_ERROR, "dosage_safety",
                        f"{name} dosage {value:.0f}mg exceeds daily safety limit of {limit_val}mg",
                        day=date, field="supplement_dosage", value=value,
                    ))
            elif "max_g" in limits:
                limit_val = limits["max_g"]
                if unit == "mg":
                    value /= 1000
                    unit = "g"
                if unit == "g" and value > limit_val:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_ERROR, "dosage_safety",
                        f"{name} dosage {value:.1f}g exceeds daily safety limit of {limit_val}g",
                        day=date, field="supplement_dosage", value=value,
                    ))
            elif "max_ml" in limits:
                limit_val = limits["max_ml"]
                if unit == "ml" and value > limit_val:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_ERROR, "dosage_safety",
                        f"{name} dosage {value:.0f}ml exceeds daily safety limit of {limit_val}ml",
                        day=date, field="supplement_dosage", value=value,
                    ))
            elif "max_iu" in limits:
                limit_val = limits["max_iu"]
                if unit == "iu" and value > limit_val:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_ERROR, "dosage_safety",
                        f"{name} dosage {value:.0f}IU exceeds daily safety limit of {limit_val}IU",
                        day=date, field="supplement_dosage", value=value,
                    ))


def validate_citation_grounding(advisory, master_findings, report):
    """checks that every source_finding_id references a real finding."""
    valid_ids = set()
    for cat, items in master_findings.get("categories", {}).items():
        if isinstance(items, list):
            for item in items:
                fid = item.get("finding_id", "")
                if fid:
                    valid_ids.add(fid)

    days = advisory.get("daily_advisories", [])
    for day in days:
        date = day.get("date", "?")
        for suggestion in day.get("top_3_suggestions", []):
            source_id = suggestion.get("source_finding_id")
            if source_id is None or source_id == "null" or source_id == "":
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_WARNING, "citation_check",
                    f"suggestion '{suggestion.get('suggestion_id', '?')}' has no source_finding_id "
                    f"(not grounded in research papers)",
                    day=date, field="source_finding_id",
                ))
            elif source_id not in valid_ids:
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_WARNING, "citation_check",
                    f"suggestion '{suggestion.get('suggestion_id', '?')}' cites '{source_id}' "
                    f"which does not exist in master findings",
                    day=date, field="source_finding_id", value=source_id,
                ))


def validate_structural_completeness(advisory, report):
    """checks that every day has all required fields."""
    required_day_fields = [
        "date", "day_number", "days_to_competition", "phase", "location",
        "day_summary", "forward_trajectory", "readiness_projection",
        "top_3_suggestions", "nutrition_protocol", "training_guidance",
        "sleep_protocol", "warnings", "improvement_candidates",
    ]

    required_summary_fields = [
        "narrative", "overall_readiness_score", "readiness_trend", "key_systems_status",
    ]

    required_trajectory_fields = [
        "next_24h", "next_3_days", "competition_readiness_projection",
    ]

    required_suggestion_fields = [
        "rank", "suggestion_id", "title", "category", "what_to_do",
        "data_trigger", "data_trigger_value", "data_trigger_threshold",
    ]

    days = advisory.get("daily_advisories", [])
    if not days:
        report.add(ValidationIssue(
            ValidationIssue.SEVERITY_ERROR, "structural",
            "advisory contains no daily_advisories",
        ))
        return

    for day in days:
        date = day.get("date", "?")
        report.days_checked += 1

        for field in required_day_fields:
            if field not in day:
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "structural",
                    f"missing required field '{field}'",
                    day=date, field=field,
                ))

        summary = day.get("day_summary", {})
        if isinstance(summary, dict):
            for field in required_summary_fields:
                if field not in summary:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_WARNING, "structural",
                        f"day_summary missing '{field}'",
                        day=date, field=f"day_summary.{field}",
                    ))

        trajectory = day.get("forward_trajectory", {})
        if isinstance(trajectory, dict):
            for field in required_trajectory_fields:
                if field not in trajectory:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_WARNING, "structural",
                        f"forward_trajectory missing '{field}'",
                        day=date, field=f"forward_trajectory.{field}",
                    ))

        suggestions = day.get("top_3_suggestions", [])
        if len(suggestions) != 3:
            report.add(ValidationIssue(
                ValidationIssue.SEVERITY_WARNING, "structural",
                f"expected 3 suggestions, found {len(suggestions)}",
                day=date, field="top_3_suggestions",
            ))

        for suggestion in suggestions:
            for field in required_suggestion_fields:
                if field not in suggestion:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_WARNING, "structural",
                        f"suggestion '{suggestion.get('suggestion_id', '?')}' missing '{field}'",
                        day=date, field=f"top_3_suggestions.{field}",
                    ))


def validate_date_coverage(advisory, report):
    """checks that all dates from start to competition are covered with no gaps."""
    days = advisory.get("daily_advisories", [])
    if not days:
        return

    dates = []
    for day in days:
        d = day.get("date")
        if d:
            try:
                dates.append(datetime.strptime(d, "%Y-%m-%d"))
            except ValueError:
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "structural",
                    f"invalid date format: '{d}'",
                    field="date", value=d,
                ))

    if len(dates) < 2:
        return

    dates.sort()
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i - 1]).days
        if gap > 1:
            report.add(ValidationIssue(
                ValidationIssue.SEVERITY_ERROR, "date_coverage",
                f"gap of {gap} days between {dates[i-1].strftime('%Y-%m-%d')} "
                f"and {dates[i].strftime('%Y-%m-%d')}",
                field="date",
            ))
        elif gap == 0:
            report.add(ValidationIssue(
                ValidationIssue.SEVERITY_ERROR, "date_coverage",
                f"duplicate date: {dates[i].strftime('%Y-%m-%d')}",
                day=dates[i].strftime("%Y-%m-%d"), field="date",
            ))


def validate_biomarker_projections(advisory, report):
    """checks that biomarker tracking projections are physiologically possible."""
    tracking = advisory.get("biomarker_tracking", {})

    ferritin = tracking.get("ferritin_projection", {})
    if ferritin:
        start = ferritin.get("start_value")
        projected = ferritin.get("projected_competition_day_value")
        if start is not None and projected is not None:
            rng = PHYSIOLOGICAL_RANGES["ferritin_ng_ml"]
            if not (rng["min"] <= projected <= rng["max"]):
                report.add(ValidationIssue(
                    ValidationIssue.SEVERITY_ERROR, "range_validation",
                    f"ferritin projection {projected} ng/ml is outside valid range "
                    f"[{rng['min']}-{rng['max']}]",
                    field="biomarker_tracking.ferritin_projection", value=projected,
                ))
            # max ferritin increase is ~2 ng/ml per day with oral supplementation
            if isinstance(start, (int, float)) and isinstance(projected, (int, float)):
                daily_increase = (projected - start) / 26.0 if projected > start else 0
                if daily_increase > 3.0:
                    report.add(ValidationIssue(
                        ValidationIssue.SEVERITY_WARNING, "consistency",
                        f"ferritin projected increase of {daily_increase:.1f} ng/ml/day "
                        f"exceeds realistic oral supplementation rate (~1-2 ng/ml/day)",
                        field="biomarker_tracking.ferritin_projection",
                        value=daily_increase,
                    ))


# =============================================================================
# main validation orchestrator
# =============================================================================

def validate_advisory(advisory, master_findings=None):
    """
    runs all validation checks on a generated advisory.

    args:
        advisory: the parsed JSON advisory dictionary
        master_findings: the master findings dictionary (for citation checks)

    returns:
        ValidationReport with all issues found
    """
    report = ValidationReport()

    # structural checks
    validate_structural_completeness(advisory, report)
    validate_date_coverage(advisory, report)

    # physiological range checks
    validate_readiness_range(advisory, report)
    validate_readiness_consistency(advisory, report)
    validate_sleep_protocol(advisory, report)
    validate_hydration(advisory, report)
    validate_training_duration(advisory, report)

    # safety checks
    validate_dosage_safety(advisory, report)
    validate_biomarker_projections(advisory, report)

    # grounding checks
    if master_findings:
        validate_citation_grounding(advisory, master_findings, report)

    return report


def validate_and_stamp(advisory, master_findings=None):
    """
    validates an advisory and stamps it with the validation report.
    returns the advisory dict with a 'validation' key added.
    """
    report = validate_advisory(advisory, master_findings)

    advisory["validation"] = report.to_dict()
    advisory["validation"]["validated_at"] = datetime.now().isoformat()

    return advisory, report
