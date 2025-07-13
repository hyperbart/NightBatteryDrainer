#!/usr/bin/env python3

from datetime import date
import requests
from datetime import datetime, timedelta
import pytz
from time import sleep
# import threading  # Removed because it's unused

if __name__ == "__main__":

    print(f"Starting battery drainer script...")

    # Function to get sunrise time for a given latitude and longitude
    def get_sunrise_time(lat, lng):
        #tomorrow = date.today() + timedelta(days=1)
        tomorrow = date.today()
        url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lng}&formatted=0&date={tomorrow}"
        response = requests.get(url)
        data = response.json()
        sunrise_utc = data['results']['sunrise']
        return sunrise_utc

    # Coordinates for your home
    latitude = xx.xxxxx
    longitude = y.yyyyy

    sunrise_time_utc = get_sunrise_time(latitude, longitude)
    # Convert sunrise time from UTC to Brussels time (CET/CEST)
    utc = pytz.utc
    brussels = pytz.timezone('Europe/Brussels')
    sunrise_dt_utc = datetime.fromisoformat(sunrise_time_utc.replace('Z', '+00:00')).replace(tzinfo=utc)
    sunrise_dt_brussels = sunrise_dt_utc.astimezone(brussels)
    print(f"Sunrise time in xxxxxxxxxxx, Belgium (Brussels time): {sunrise_dt_brussels.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Get current battery state of charge (SOC) from API
    soc_url = "http://x.y.z.a:1234/api/state?jq=.battery[0].soc"
    soc_response = requests.get(soc_url)
    soc = int(soc_response.text.strip())

    # Battery parameters
    battery_capacity_kwh = 15
    battery_limit_percent = 10
    usable_battery_kwh = battery_capacity_kwh * (soc - battery_limit_percent) / 100

    # Load parameters
    # Duration (in seconds) to sample homePower for averaging
    standby_sample_minutes = 15  # Set minutes to sample for standby power
    standby_sample_seconds = standby_sample_minutes * 60

    home_power_url = "http://x.y.z.a:1234/api/state?jq=.homePower"
    home_power_samples = []

    print(f"Sampling homePower every second for {standby_sample_minutes} minutes to calculate average standby power...")

    for _ in range(standby_sample_seconds):
        try:
            resp = requests.get(home_power_url)
            power = float(resp.text.strip())
            home_power_samples.append(power)
        except Exception as e:
            print(f"Error sampling homePower: {e}")
        sleep(1)

    if home_power_samples:
        calculated_standby_kw = sum(home_power_samples) / len(home_power_samples) / 1000  # Convert W to kW
        print("Standby power samples collected and average calculated.")
    else:
        calculated_standby_kw = 2.0  # fallback value, set high enough to avoid issues if no samples were taken as to not drain the battery
        print("No samples collected for standby power. Using fallback value.")

    standby_kw = calculated_standby_kw
    print(f"Calculated average standby power: {standby_kw:.3f} kW")
    
    
    

    # Get minCurrent from EVCC API and calculate extra_load_kw_dynamic
    min_current_url = "http://x.y.z.a:1234/api/state?jq=.loadpoints[0].minCurrent"
    min_current_response = requests.get(min_current_url)
    min_current = int(min_current_response.text.strip())
    extra_load_kw_dynamic = (min_current * 230) / 1000  # Convert to kW
    #extra_load_kw_dynamic = 0.2 # Set to a fixed value for testing
    print(f"Dynamic extra load: {extra_load_kw_dynamic:.2f} kW")


    # Check if standby power alone will deplete the battery before sunrise
    if standby_kw > 0:
        depletion_time_standby_hours = usable_battery_kwh / standby_kw
    else:
        depletion_time_standby_hours = float('inf')

    time_until_sunrise_hours = (sunrise_dt_brussels - datetime.now(brussels)).total_seconds() / 3600

    print(f"Depletion time at standby power only: {depletion_time_standby_hours:.2f} hours")
    print(f"Time until sunrise: {time_until_sunrise_hours:.2f} hours")

    if depletion_time_standby_hours < time_until_sunrise_hours:
        print("Warning: Standby power alone will deplete the battery before sunrise. Not starting extra load.")
        exit(0)
    else:
        print("Sufficient battery to support extra load until sunrise.")

        # Use the dynamic extra load and add it to the standby load to calculate total load
        total_load_kw = standby_kw + extra_load_kw_dynamic


        # Calculate how many kWh can be used before reaching the limit
        energy_to_use_kwh = usable_battery_kwh

        # Calculate how long (in hours) it takes to deplete the battery to the limit at the increased load
        depletion_time_hours = energy_to_use_kwh / total_load_kw
        print(f"Depletion time at {total_load_kw} kW load: {depletion_time_hours:.2f} hours")

        # Calculate the time to activate the load so the battery reaches the limit at sunrise
        activation_time_brussels = sunrise_dt_brussels - timedelta(hours=depletion_time_hours)

        print(f"Current battery SOC: {soc}%")
        print(f"Activate the {extra_load_kw_dynamic}kW load at: {activation_time_brussels.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Calculate seconds to sleep until activation time
        now_brussels = datetime.now(brussels)
        seconds_to_sleep = (activation_time_brussels - now_brussels).total_seconds()

        if seconds_to_sleep > 0:
            print(f"Sleeping for {seconds_to_sleep:.0f} seconds until activation time...")
            sleep(seconds_to_sleep)
        else:
            print("Activation time is in the past. Sending POST immediately.")


        # Send POST request to activate the load
        post_url = "http://x.y.z.a:1234/api/loadpoints/1/mode/minpv"
        try:
            post_response = requests.post(post_url)
            print(f"POST sent. Response status: {post_response.status_code}, body: {post_response.text}")   
        except Exception as e:
            print(f"Failed to send POST request: {e}")


        while True:
            try:
                soc_response = requests.get(soc_url)
                current_soc = int(soc_response.text.strip())
                print(f"Periodic SOC check: {current_soc}%")
                if current_soc <= battery_limit_percent:
                    print(f"SOC reached limit ({battery_limit_percent}%). Sending POST to stop extra load.")
                    stop_post_url = "http://x.y.z.a:1234/api/loadpoints/1/mode/pv"
                    try:
                        stop_post_response = requests.post(stop_post_url)
                        print(f"Stop POST sent. Response status: {stop_post_response.status_code}, body: {stop_post_response.text}")
                    except Exception as e:
                        print(f"Failed to send stop POST request: {e}")
                    break
            except Exception as e:
                print(f"Error checking SOC: {e}")
            sleep(60)  # Check every 60 seconds

