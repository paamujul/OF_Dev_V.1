"""
athlete profile data structure.
aggregates bio, wearable, bloodwork, and travel data into a single object.
"""

import json
import math
import statistics
from config.settings import hrv_long_window, hrv_short_window, min_readings_req


class athleteprofile:
    """unified athlete data container for pipeline consumption."""

    def __init__(self, bio, wearables, bloodwork, travel):
        self.bio = bio
        self.wearables = wearables
        self.bloodwork = bloodwork
        self.travel = travel

    def today_hrv(self):
        return self.wearables["hrv_rmssd_30d"][-1]

    def hrv_window(self):
        history = self.wearables["hrv_rmssd_30d"]
        if len(history) >= hrv_long_window:
            return history[-hrv_long_window:]
        elif len(history) >= min_readings_req:
            return history[-hrv_short_window:]
        else:
            raise ValueError(
                f"{self.bio['name']} needs at least {min_readings_req} readings."
            )

    def hrv_baseline(self):
        return statistics.mean(self.hrv_window())

    def hrv_std(self):
        return statistics.stdev(self.hrv_window())

    def ln_rmssd_series(self):
        return [math.log(v) for v in self.hrv_window()]

    def avg_sleep_efficiency(self):
        return statistics.mean(self.wearables["sleep_efficiency_7d"])

    def avg_total_sleep_time(self):
        return statistics.mean(self.wearables["total_sleep_time_7d"])

    def avg_skin_temp(self):
        return statistics.mean(self.wearables["skin_temp_celsius_7d"])

    def timezone_shift(self):
        return self.travel["flight"]["timezone_shift"]

    def direction(self):
        return self.travel["flight"]["direction"]

    def altitude_delta(self):
        dest = self.travel["destination"]["altitude_m"]
        origin = self.travel["origin"]["altitude_m"]
        return max(0, dest - origin)

    def avg_respiratory_rate(self):
        return statistics.mean(self.wearables["respiratory_rate_7d"])

    def respiratory_rate_std(self):
        return statistics.stdev(self.wearables["respiratory_rate_7d"])

    def sleep_debt(self):
        return self.wearables.get("sleep_debt_3d_hours", 0.0)

    def avg_deep_rem_percent(self):
        return statistics.mean(self.wearables["deep_rem_percent_7d"])

    def avg_rem_percent(self):
        return statistics.mean(self.wearables["rem_percent_7d"])

    def baseline_rem_percent(self):
        values = self.wearables["rem_percent_7d"]
        return statistics.mean(values[:4]) if len(values) >= 4 else statistics.mean(values)

    def nighttime_skin_temps(self):
        return self.wearables.get("nighttime_skin_temp", [])

    def nighttime_rhrs(self):
        return self.wearables.get("nighttime_rhr", [])

    def spo2_baseline(self):
        return self.wearables.get("spo2_baseline", 97.0)

    def spo2_transit(self):
        return self.wearables.get("spo2_transit", 97.0)

    def strain(self):
        return self.wearables.get("strain_last_session", 0.0)

    def hr_zone_minutes(self):
        return self.wearables.get("hr_zone_minutes", {})

    def peak_strain_hour(self):
        return self.wearables.get("peak_strain_hour", 12.0)

    def active_minutes_inflight(self):
        return self.wearables.get("active_minutes_inflight", 0)

    def resting_hr_mean(self):
        return statistics.mean(self.wearables["resting_hr_7d"])

    def resting_hr_std(self):
        return statistics.stdev(self.wearables["resting_hr_7d"])

    def avg_deep_sleep_percent(self):
        return statistics.mean(self.wearables["deep_sleep_percent_7d"])

    def avg_spo2(self):
        return statistics.mean(self.wearables["spo2_7d"])

    def session_duration(self):
        return self.wearables.get("session_duration_minutes", 0)

    def active_energy(self):
        return self.wearables.get("active_energy_kcal_last_session", 0)

    def active_hr(self):
        return self.wearables.get("active_hr_bpm_last_session", 0)

    def hr_zone45_minutes(self):
        zones = self.hr_zone_minutes()
        return zones.get("zone4", 0) + zones.get("zone5", 0)


def load_athlete(bio_path, wearable_path, bloodwork_path, travel_path):
    """loads all json sources and returns an athleteprofile instance."""
    with open(bio_path, "r") as f:
        bio = json.load(f)
    with open(wearable_path, "r") as f:
        wearables = json.load(f)
    with open(bloodwork_path, "r") as f:
        bloodwork = json.load(f)
    with open(travel_path, "r") as f:
        travel = json.load(f)
    return athleteprofile(bio, wearables, bloodwork, travel)

