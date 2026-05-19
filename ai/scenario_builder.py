"""
competition scenario builder.
automatically computes all scenario parameters from origin city,
destination city, travel date, and competition date.

uses the open-meteo geocoding api to resolve any city name into
coordinates, altitude, timezone, and country. uses the open-meteo
archive api for real climate data and haversine distance for flight
duration estimation. pulls athlete info from the pipeline data files.
"""

import os
import json
import math
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cache_dir = os.path.join(base_dir, "ai", "cache")
city_cache_path = os.path.join(cache_dir, "city_cache.json")


def load_city_cache():
    """loads the local city cache from disk."""
    if os.path.exists(city_cache_path):
        with open(city_cache_path, "r") as f:
            return json.load(f)
    return {}


def save_city_cache(cache):
    """persists the city cache to disk."""
    os.makedirs(cache_dir, exist_ok=True)
    with open(city_cache_path, "w") as f:
        json.dump(cache, f, indent=2)


def utc_offset_from_iana(tz_iana, ref_date=None):
    """
    computes the utc offset in hours from an iana timezone string.
    uses a reference date to account for dst.
    """
    if ref_date is None:
        ref_date = datetime.now()
    elif isinstance(ref_date, str):
        ref_date = datetime.strptime(ref_date, "%Y-%m-%d")

    try:
        tz = ZoneInfo(tz_iana)
        offset = ref_date.replace(tzinfo=tz).utcoffset()
        return offset.total_seconds() / 3600.0
    except Exception:
        return 0.0


def tz_abbreviation(tz_iana, ref_date=None):
    """gets the short timezone abbreviation (e.g. IST, AST) from an iana timezone."""
    if ref_date is None:
        ref_date = datetime.now()
    elif isinstance(ref_date, str):
        ref_date = datetime.strptime(ref_date, "%Y-%m-%d")

    try:
        tz = ZoneInfo(tz_iana)
        return ref_date.replace(tzinfo=tz).strftime("%Z")
    except Exception:
        return tz_iana


def geocode_city(city_name):
    """
    resolves a city name to coordinates, altitude, timezone, and country
    using the open-meteo geocoding api (free, no auth required).

    returns a dict with: lat, lon, alt_m, tz_iana, tz_name, utc_offset, country
    returns none if the city cannot be resolved.
    """
    cache = load_city_cache()
    key = city_name.lower().strip()

    if key in cache:
        return cache[key]

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "en"}

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                r = results[0]
                tz_iana = r.get("timezone", "UTC")
                utc_offset = utc_offset_from_iana(tz_iana)
                tz_abbr = tz_abbreviation(tz_iana)
                country = r.get("country", "unknown").lower()

                city_data = {
                    "lat": r["latitude"],
                    "lon": r["longitude"],
                    "alt_m": r.get("elevation", 0),
                    "tz_iana": tz_iana,
                    "tz_name": tz_abbr,
                    "utc_offset": utc_offset,
                    "country": country,
                    "population": r.get("population", 0),
                    "resolved_name": r.get("name", city_name),
                }

                cache[key] = city_data
                save_city_cache(cache)

                return city_data
    except Exception as e:
        print(f"  geocoding api warning for '{city_name}': {e}")

    return None


def haversine_km(lat1, lon1, lat2, lon2):
    """computes great-circle distance between two points in km."""
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_flight_hours(distance_km):
    """estimates flight duration from distance. avg cruise 850 km/h + 1h for taxi/climb/descent."""
    return round(distance_km / 850.0 + 1.0, 1)


def compute_timezone_shift(origin_offset, dest_offset):
    """computes timezone shift and direction."""
    shift = dest_offset - origin_offset
    if abs(shift) > 12:
        shift = shift - 24 if shift > 0 else shift + 24
    direction = "east" if shift > 0 else "west" if shift < 0 else "none"
    return shift, direction


def fetch_climate_data(lat, lon, month):
    """
    fetches historical climate averages from open-meteo for the target month.
    uses the previous year's data as a proxy for expected conditions.
    """
    year = datetime.now().year - 1
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)
    end = end_date.strftime("%Y-%m-%d")

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_mean,relative_humidity_2m_mean",
        "timezone": "auto",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            daily = data.get("daily", {})
            temps = [t for t in daily.get("temperature_2m_mean", []) if t is not None]
            maxtemps = [t for t in daily.get("temperature_2m_max", []) if t is not None]
            humids = [h for h in daily.get("relative_humidity_2m_mean", []) if h is not None]
            if temps and humids:
                avg_temp = round(sum(temps) / len(temps), 1)
                avg_max = round(sum(maxtemps) / len(maxtemps), 1) if maxtemps else avg_temp
                avg_humid = round(sum(humids) / len(humids), 1)
                return {
                    "avg_temp_celsius": avg_temp,
                    "avg_max_temp_celsius": avg_max,
                    "avg_humidity_percent": avg_humid,
                    "source": "open_meteo_archive",
                }
    except Exception as e:
        print(f"  climate api warning: {e}")

    return None


def estimate_ewbgt(temp_c, humidity_pct):
    """
    estimates environmental wet-bulb globe temperature.
    simplified liljegren approximation for outdoor conditions.
    """
    e = (humidity_pct / 100.0) * 6.105 * math.exp((17.27 * temp_c) / (237.7 + temp_c))
    tw = temp_c * math.atan(0.151977 * (humidity_pct + 8.313659) ** 0.5) + \
         math.atan(temp_c + humidity_pct) - math.atan(humidity_pct - 1.676331) + \
         0.00391838 * humidity_pct ** 1.5 * math.atan(0.023101 * humidity_pct) - 4.686035
    ewbgt = 0.7 * tw + 0.2 * (temp_c + 2) + 0.1 * temp_c
    return round(ewbgt, 1)


def compute_phases(start_date, travel_date, competition_date):
    """automatically generates training phases based on the timeline."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    travel = datetime.strptime(travel_date, "%Y-%m-%d")
    comp = datetime.strptime(competition_date, "%Y-%m-%d")

    total_pre_travel = (travel - start).days
    post_travel = (comp - travel).days

    phases = []

    if total_pre_travel >= 21:
        base_end = start + timedelta(days=total_pre_travel - 11)
        sharp_end = base_end + timedelta(days=7)
        taper_end = travel - timedelta(days=1)

        phases.append({
            "name": "pre_travel_base",
            "dates": f"{start.strftime('%Y-%m-%d')} to {(base_end - timedelta(days=1)).strftime('%Y-%m-%d')}",
            "days": (base_end - start).days,
            "focus": "baseline optimization, supplementation loading, heat pre-acclimation, sleep architecture repair",
        })
        phases.append({
            "name": "pre_travel_sharpening",
            "dates": f"{base_end.strftime('%Y-%m-%d')} to {(sharp_end - timedelta(days=1)).strftime('%Y-%m-%d')}",
            "days": (sharp_end - base_end).days,
            "focus": "intensity tapering begins, circadian pre-shift, continued supplementation, technique sharpening",
        })
        phases.append({
            "name": "pre_travel_taper",
            "dates": f"{sharp_end.strftime('%Y-%m-%d')} to {taper_end.strftime('%Y-%m-%d')}",
            "days": (travel - sharp_end).days,
            "focus": "full taper, final circadian alignment, nutrition loading, mental prep",
        })
    elif total_pre_travel >= 14:
        base_end = start + timedelta(days=total_pre_travel - 7)
        taper_end = travel - timedelta(days=1)

        phases.append({
            "name": "pre_travel_base",
            "dates": f"{start.strftime('%Y-%m-%d')} to {(base_end - timedelta(days=1)).strftime('%Y-%m-%d')}",
            "days": (base_end - start).days,
            "focus": "baseline optimization, supplementation, heat acclimation, circadian pre-shift",
        })
        phases.append({
            "name": "pre_travel_taper",
            "dates": f"{base_end.strftime('%Y-%m-%d')} to {taper_end.strftime('%Y-%m-%d')}",
            "days": (travel - base_end).days,
            "focus": "full taper, circadian alignment, nutrition loading, mental prep",
        })
    else:
        taper_end = travel - timedelta(days=1)
        phases.append({
            "name": "pre_travel_compressed",
            "dates": f"{start.strftime('%Y-%m-%d')} to {taper_end.strftime('%Y-%m-%d')}",
            "days": total_pre_travel,
            "focus": "compressed prep, essential supplementation, circadian pre-shift, reduced training",
        })

    phases.append({
        "name": "travel_day",
        "dates": travel.strftime("%Y-%m-%d"),
        "days": 1,
        "focus": "in-flight protocols, hydration, venous stasis prevention, circadian lock-in",
    })

    if post_travel > 1:
        adapt_end = comp - timedelta(days=1)
        phases.append({
            "name": "adaptation",
            "dates": f"{(travel + timedelta(days=1)).strftime('%Y-%m-%d')} to {adapt_end.strftime('%Y-%m-%d')}",
            "days": post_travel - 1,
            "focus": "destination adaptation, heat exposure, venue familiarization, light training",
        })

    phases.append({
        "name": "competition",
        "dates": comp.strftime("%Y-%m-%d"),
        "days": 1,
        "focus": "competition day protocols, precooling, warm-up, execution",
    })

    return phases


def load_athlete_info():
    """loads athlete name and sport from pipeline data files."""
    bio_path = os.path.join(base_dir, "data", "backtest", "athlete_bio.json")
    if os.path.exists(bio_path):
        with open(bio_path, "r") as f:
            bio = json.load(f)
        return {
            "name": bio.get("name", "unknown"),
            "weight_kg": bio.get("weight_kg"),
            "height_cm": bio.get("height_cm"),
            "age": bio.get("age"),
            "sport": bio.get("sport", "athletics"),
        }
    return {"name": "unknown", "sport": "athletics"}


def build_scenario(origin_city, destination_city, travel_date, competition_date, start_date=None):
    """
    builds a complete competition scenario from minimal inputs.

    args:
        origin_city: name of any city (resolved via geocoding api)
        destination_city: name of any city (resolved via geocoding api)
        travel_date: "YYYY-MM-DD" format
        competition_date: "YYYY-MM-DD" format
        start_date: optional "YYYY-MM-DD", defaults to today

    returns:
        complete scenario dictionary with all computed values
    """
    print(f"  resolving origin: {origin_city}...")
    origin = geocode_city(origin_city)
    if origin is None:
        raise ValueError(f"could not resolve origin city '{origin_city}' via geocoding api")

    print(f"    {origin['resolved_name']}, {origin['country']} | "
          f"lat: {origin['lat']}, lon: {origin['lon']} | "
          f"alt: {origin['alt_m']}m | tz: {origin['tz_name']} (UTC{origin['utc_offset']:+.1f})")

    print(f"  resolving destination: {destination_city}...")
    dest = geocode_city(destination_city)
    if dest is None:
        raise ValueError(f"could not resolve destination city '{destination_city}' via geocoding api")

    print(f"    {dest['resolved_name']}, {dest['country']} | "
          f"lat: {dest['lat']}, lon: {dest['lon']} | "
          f"alt: {dest['alt_m']}m | tz: {dest['tz_name']} (UTC{dest['utc_offset']:+.1f})")

    if start_date is None:
        start_date = datetime.now().strftime("%Y-%m-%d")

    comp_date = datetime.strptime(competition_date, "%Y-%m-%d")
    comp_month = comp_date.month

    distance_km = haversine_km(origin["lat"], origin["lon"], dest["lat"], dest["lon"])
    flight_hours = estimate_flight_hours(distance_km)
    tz_shift, direction = compute_timezone_shift(origin["utc_offset"], dest["utc_offset"])
    phases = compute_phases(start_date, travel_date, competition_date)

    athlete = load_athlete_info()

    print(f"  fetching climate data for {dest['resolved_name']} (month {comp_month})...")
    dest_climate = fetch_climate_data(dest["lat"], dest["lon"], comp_month)

    print(f"  fetching climate data for {origin['resolved_name']} (month {comp_month})...")
    origin_climate = fetch_climate_data(origin["lat"], origin["lon"], comp_month)

    if dest_climate:
        dest_avg_temp = dest_climate["avg_max_temp_celsius"]
        dest_avg_humid = dest_climate["avg_humidity_percent"]
    else:
        dest_avg_temp = 35.0
        dest_avg_humid = 50.0

    if origin_climate:
        origin_avg_temp = origin_climate["avg_max_temp_celsius"]
        origin_avg_humid = origin_climate["avg_humidity_percent"]
    else:
        origin_avg_temp = 30.0
        origin_avg_humid = 50.0

    ewbgt = estimate_ewbgt(dest_avg_temp, dest_avg_humid)

    scenario = {
        "athlete_name": athlete["name"],
        "sport": athlete.get("sport", "athletics"),
        "origin": {
            "city": origin["resolved_name"].lower(),
            "country": origin["country"],
            "timezone": origin["tz_name"],
            "timezone_iana": origin["tz_iana"],
            "utc_offset_hours": origin["utc_offset"],
            "latitude": origin["lat"],
            "longitude": origin["lon"],
            "altitude_m": origin["alt_m"],
            "avg_temp_celsius": origin_avg_temp,
            "avg_humidity_percent": origin_avg_humid,
        },
        "destination": {
            "city": dest["resolved_name"].lower(),
            "country": dest["country"],
            "timezone": dest["tz_name"],
            "timezone_iana": dest["tz_iana"],
            "utc_offset_hours": dest["utc_offset"],
            "latitude": dest["lat"],
            "longitude": dest["lon"],
            "altitude_m": dest["alt_m"],
            "avg_temp_celsius": dest_avg_temp,
            "avg_humidity_percent": dest_avg_humid,
            "ewbgt_expected": ewbgt,
        },
        "travel_date": travel_date,
        "competition_date": competition_date,
        "start_date": start_date,
        "distance_km": round(distance_km, 1),
        "timezone_shift_hours": tz_shift,
        "direction": direction,
        "flight_duration_hours": flight_hours,
        "phases": phases,
    }

    return scenario
