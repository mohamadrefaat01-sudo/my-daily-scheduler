import os
import json
import requests
import arrow
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURATION ---
CITY = "Cairo"
COUNTRY = "Egypt"
METHOD = 5  # Egyptian General Authority
CALENDAR_ID = os.environ.get("CALENDAR_ID")
SERVICE_ACCOUNT_JSON = os.environ.get("GCP_SA_KEY")

# Define the routine
routine = {
    # Anchor: Which prayer is this tied to?
    # Offset: How many minutes BEFORE (-) or AFTER (+)?
    
    "Mutoon Memorization": {"anchor": "Fajr", "offset": 30, "duration": 30},
    "Business Development": {"anchor": "Fajr", "offset": 90, "duration": 60},
    "Deep Work Session 1": {"anchor": "Fajr", "offset": 160, "duration": 120},
    
    "Power Nap (Qailulah)": {"anchor": "Dhuhr", "offset": -45, "duration": 20},
    "Quran Memorization": {"anchor": "Dhuhr", "offset": 20, "duration": 60},
    
    "Deep Work Session 2": {"anchor": "Asr", "offset": -150, "duration": 120},
    "Quran Testing": {"anchor": "Asr", "offset": 20, "duration": 15},
    
    # --- NEW: EXERCISE BLOCK ---
    # 90 mins BEFORE Maghrib. Gives you 1 hour to train + 30 mins to shower/wudu.
    "Exercise / Gym": {"anchor": "Maghrib", "offset": -90, "duration": 60},
    
    "Islamic Reading": {"anchor": "Maghrib", "offset": 30, "duration": 60},
}

# Tasks to SKIP on Fridays (Exercise is NOT skipped, so you stay healthy!)
FRIDAY_EXCLUSIONS = ["Mutoon Memorization", "Quran Memorization", "Quran Testing"]

def get_prayer_times():
    today = arrow.now()
    url = f"http://api.aladhan.com/v1/calendarByCity?city={CITY}&country={COUNTRY}&method={METHOD}&month={today.month}&year={today.year}"
    return requests.get(url).json()['data']

def main():
    if not SERVICE_ACCOUNT_JSON:
        print("Error: No Google Key found!")
        return

    creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=['https://www.googleapis.com/auth/calendar']
    )
    service = build('calendar', 'v3', credentials=creds)

    print("Fetching Prayer Times...")
    prayer_data = get_prayer_times()

    for day_data in prayer_data:
        date_str = day_data['date']['readable']
        timings = day_data['timings']
        for prayer in timings: timings[prayer] = timings[prayer].split(' ')[0]
        today_date = arrow.get(date_str, "DD MMM YYYY")
        
        # Only schedule future dates
        if today_date < arrow.now().shift(days=-1): continue

        is_friday = today_date.weekday() == 4
        
        anchors = {
            "Fajr": arrow.get(f"{date_str} {timings['Fajr']}", "DD MMM YYYY HH:mm"),
            "Dhuhr": arrow.get(f"{date_str} {timings['Dhuhr']}", "DD MMM YYYY HH:mm"),
            "Asr": arrow.get(f"{date_str} {timings['Asr']}", "DD MMM YYYY HH:mm"),
            "Maghrib": arrow.get(f"{date_str} {timings['Maghrib']}", "DD MMM YYYY HH:mm"),
            "Isha": arrow.get(f"{date_str} {timings['Isha']}", "DD MMM YYYY HH:mm"),
        }

        for task_name, rules in routine.items():
            if is_friday and task_name in FRIDAY_EXCLUSIONS: continue

            anchor_time = anchors.get(rules['anchor'])
            if anchor_time:
                start_time = anchor_time.shift(minutes=rules['offset'])
                end_time = start_time.shift(minutes=rules['duration'])

                event = {
                    'summary': task_name,
                    'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Africa/Cairo'},
                    'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Africa/Cairo'},
                    'description': 'Productivity Bot'
                }
                try:
                    service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
                    print(f"Added {task_name} on {date_str}")
                except Exception as e:
                    print(f"Error: {e}")

if __name__ == "__main__":
    main()
