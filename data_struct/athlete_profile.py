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
