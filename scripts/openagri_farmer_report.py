import requests
from datetime import datetime, timezone, timedelta

# ------------------------------------------------
# CONFIG
# ------------------------------------------------

API_KEY = "413f5263fc5c7eb65c41890f7b0ed02a"  # <-- put your key here

# Rethymno, Crete (approx)
LAT = 35.3655
LON = 24.4823

ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"

# Base temperatures (°C) for GDD
CROP_GDD_BASE = {
    "olives": 10.0,
    "grapes": 10.0,
    "vegetables": 5.0,  # generic base, varies by crop
}

# Spray advisory thresholds
MAX_WIND_OPTIMAL = 5.0   # m/s
MAX_WIND_MARGINAL = 7.5  # m/s
MAX_POP_OPTIMAL = 0.3    # 30% rain chance
MAX_POP_MARGINAL = 0.6   # 60% rain chance


# ------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------

def to_local_time(ts, offset_seconds):
    """Convert UNIX timestamp + timezone offset to local time string (dd|mm|yyyy HH:MM)."""
    utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    local_dt = utc_dt + timedelta(seconds=offset_seconds)
    return local_dt.strftime("%d|%m|%Y %H:%M")


def wind_direction_from_deg(deg):
    if deg is None:
        return "unknown"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((deg + 22.5) // 45) % 8
    return dirs[idx]


def beaufort_scale(speed_ms):
    """Rough Beaufort description from m/s."""
    if speed_ms is None:
        return "unknown"
    s = speed_ms
    if s < 0.3:
        return "Calm"
    elif s < 3.4:
        return "Light breeze"
    elif s < 5.5:
        return "Gentle breeze"
    elif s < 8.0:
        return "Moderate breeze"
    elif s < 10.8:
        return "Fresh breeze"
    elif s < 13.9:
        return "Strong breeze"
    elif s < 17.2:
        return "Near gale"
    elif s < 20.8:
        return "Gale"
    else:
        return "Storm / violent gale"


def calculate_thi(temp_c, rh):
    """
    Temperature–Humidity Index (THI) using common formula in °F.
    Useful as a general heat stress indicator.
    """
    if temp_c is None or rh is None:
        return None
    temp_f = temp_c * 9 / 5 + 32
    thi = temp_f - (0.55 - 0.0055 * rh) * (temp_f - 58)
    return thi


def classify_thi(thi):
    if thi is None:
        return "No data"
    if thi < 68:
        return "No heat stress"
    elif thi < 72:
        return "Mild heat stress"
    elif thi < 80:
        return "Moderate heat stress"
    else:
        return "Severe heat stress"


def classify_spray_window(hour_data):
    """
    Simple spray advisory based on wind, rain amount and rain probability.
    """
    wind = hour_data.get("wind_speed", 0.0)
    pop = hour_data.get("pop", 0.0)  # probability of precipitation (0..1)
    rain_amount = 0.0
    if "rain" in hour_data:
        rain_amount = hour_data["rain"].get("1h", 0.0)

    # If it's raining at that hour → always unsuitable
    if rain_amount > 0:
        return "UNSUITABLE"

    if wind > MAX_WIND_MARGINAL or pop > MAX_POP_MARGINAL:
        return "UNSUITABLE"
    elif wind > MAX_WIND_OPTIMAL or pop > MAX_POP_OPTIMAL:
        return "MARGINAL"
    else:
        return "OPTIMAL"


def compute_gdd_from_daily(daily_list, base_temp):
    """
    Compute GDD from daily forecast using (Tmax + Tmin)/2 - base.
    One Call daily has temp.min and temp.max.
    """
    result = []
    for d in daily_list:
        temp = d.get("temp", {})
        tmin = temp.get("min")
        tmax = temp.get("max")
        dt_ts = d.get("dt")
        if tmin is None or tmax is None or dt_ts is None:
            continue
        tavg = (tmin + tmax) / 2.0
        gdd = max(0.0, tavg - base_temp)
        result.append({
            "date_ts": dt_ts,
            "tmin": round(tmin, 1),
            "tmax": round(tmax, 1),
            "gdd": round(gdd, 1),
        })
    return result


# ------------------------------------------------
# MAIN FETCH
# ------------------------------------------------

def fetch_onecall():
    params = {
        "lat": LAT,
        "lon": LON,
        "appid": API_KEY,
        "units": "metric",
        "exclude": "minutely",
    }
    resp = requests.get(ONECALL_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def print_farmer_report():
    print("=== Farmer Weather Report (OpenWeather) ===")
    print(f"Location approx: Rethymno, Crete (lat={LAT:.4f}, lon={LON:.4f})\n")

    try:
        data = fetch_onecall()
    except Exception as e:
        print(f"ERROR: Could not get data from OpenWeather: {e}")
        return

    current = data.get("current", {})
    hourly = data.get("hourly", [])
    daily = data.get("daily", [])
    tz_offset = data.get("timezone_offset", 0)

    # ------------------ CURRENT ------------------
    print(">>> Current conditions")
    dt = current.get("dt")
    if dt is not None:
        print("  Time (local):", to_local_time(dt, tz_offset))

    temp = current.get("temp")
    feels_like = current.get("feels_like")
    rh = current.get("humidity")
    pressure = current.get("pressure")
    uvi = current.get("uvi")
    clouds = current.get("clouds")
    vis = current.get("visibility")
    wind_speed = current.get("wind_speed")
    wind_deg = current.get("wind_deg")
    weather_list = current.get("weather", [])
    description = weather_list[0]["description"] if weather_list else "N/A"

    print(f"  Air temperature:     {temp} °C (feels like {feels_like} °C)")
    print(f"  Relative humidity:   {rh} %")
    print(f"  Pressure:            {pressure} hPa")
    print(f"  Cloud cover:         {clouds} %")
    print(f"  Visibility:          {vis} m")
    print(f"  UV Index:            {uvi}")
    print(f"  Wind speed:          {wind_speed} m/s ({beaufort_scale(wind_speed)})")
    print(f"  Wind direction:      {wind_direction_from_deg(wind_deg)} ({wind_deg}°)")
    print(f"  Conditions:          {description}")

    thi = calculate_thi(temp, rh)
    print("\n>>> Heat stress indicator (THI)")
    if thi is not None:
        print(f"  THI:                 {thi:.1f}  -> {classify_thi(thi)}")
    else:
        print("  THI:                 not available")

    # ------------------ SPRAY ADVISORY ------------------
    print("\n>>> Spraying advisory (next hours)")
    if not hourly:
        print("  No hourly forecast data available.")
    else:
        # Show next 8 hours
        for h in hourly[:8]:
            hdt = h.get("dt")
            time_str = to_local_time(hdt, tz_offset) if hdt else "?"
            wind = h.get("wind_speed", 0.0)
            pop = h.get("pop", 0.0)
            rain = 0.0
            if "rain" in h:
                rain = h["rain"].get("1h", 0.0)
            cond = classify_spray_window(h)
            desc = h.get("weather", [{}])[0].get("description", "N/A")

            print(
                f"  {time_str}: {cond:<10}"
                f" | wind={wind:.1f} m/s, rain={rain:.1f} mm, pop={int(pop*100)}%, {desc}"
            )
        print("  NOTE: Prefer 'OPTIMAL' windows for spraying (low wind, low rain chance).")

    # ------------------ GDD FOR CROPS ------------------
    print("\n>>> Growing Degree Days (GDD) – forecast")
    if not daily:
        print("  No daily forecast data available.")
    else:
        for crop, base in CROP_GDD_BASE.items():
            gdd_list = compute_gdd_from_daily(daily[:5], base)
            print(f"\n  {crop.capitalize()} (base {base} °C):")
            if not gdd_list:
                print("    No GDD data available.")
                continue
            for d in gdd_list:
                utc_dt = datetime.fromtimestamp(d["date_ts"], tz=timezone.utc)
                local_dt = utc_dt + timedelta(seconds=tz_offset)
                date_str = local_dt.strftime("%d|%m|%Y")
                print(
                    f"    {date_str}: Tmin={d['tmin']} °C, "
                    f"Tmax={d['tmax']} °C, GDD={d['gdd']}"
                )

    print("\nReport complete.\n")


if __name__ == "__main__":
    print_farmer_report()

