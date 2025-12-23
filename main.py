import os
import time
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

# --- COLOR PALETTE ---
C_GREEN   = "10"
C_RED     = "11"
C_PEACOCK = "7" 
C_GREY    = "8"

# --- CLEANUP LIST ---
TASKS_TO_CLEAN = [
    "Mutoon Memorization", "Business Development", 
    "Deep Work Session 1", "Deep Work Session 2", 
    "Work Session 1", "Work Session 2", "Work Session 3",
    "Power Nap (Qailulah)", "Quran Memorization", "Quran Testing",
    "Exercise / Gym", "Islamic Reading",
    "Fajr Prayer", "Dhuhr Prayer", "Asr Prayer", "Maghrib Prayer", "Isha Prayer",
    "Jumu'ah Prayer", "Class (Weekly)", "Commute to Class", "Commute Home",
    "Friday Work Session 1", "Friday Work Session 2",
    "Qiyam (Night Prayer)"  # <--- Added to cleanup
]

# --- THE DAILY ROUTINE (Ideal Durations) ---
routine = {
    # --- QIYAM (New) ---
    # Starts 60 mins before Fajr. Ends exactly at Fajr.
    "Qiyam (Night Prayer)": {"anchor": "Fajr", "offset": -60, "duration": 60, "color": C_GREEN},

    # --- PRAYERS ---
    "Fajr Prayer":   {"anchor": "Fajr", "offset": 0, "duration": 55, "color": C_GREEN},
    "Dhuhr Prayer":  {"anchor": "Dhuhr", "offset": 0, "duration": 45, "color": C_GREEN},
    "Asr Prayer":    {"anchor": "Asr", "offset": 0, "duration": 45, "color": C_GREEN},
    "Maghrib Prayer":{"anchor": "Maghrib", "offset": 0, "duration": 42, "color": C_GREEN},
    "Isha Prayer":   {"anchor": "Isha", "offset": 0, "duration": 45, "color": C_GREEN},

    # --- MORNING ---
    "Mutoon Memorization": {"anchor": "Fajr", "offset": 60, "duration": 30, "color": C_PEACOCK},
    "Work Session 1": {"anchor": "Fajr", "offset": 95, "duration": 90, "color": C_RED}, 
    "Business Development": {"anchor": "Fajr", "offset": 190, "duration": 60, "color": C_RED},
    "Work Session 2": {"anchor": "Fajr", "offset": 255, "duration": 90, "color": C_RED}, 
    
    # --- MID-DAY ---
    "Power Nap (Qailulah)": {"anchor": "Dhuhr", "offset": -45, "duration": 20, "color": C_GREEN},
    "Quran Memorization": {"anchor": "Dhuhr", "offset": 50, "duration": 60, "color": C_PEACOCK}, 

    # --- AFTERNOON ---
    "Quran Testing": {"anchor": "Asr", "offset": 50, "duration": 15, "color": C_PEACOCK},
    "Exercise / Gym": {"anchor": "Maghrib", "offset": -50, "duration": 30, "color": C_GREY},
    
    # --- EVENING ---
    "Islamic Reading": {"anchor": "Isha", "offset": 50, "duration": 60, "color": C_PEACOCK},
    "Work Session 3": {"anchor": "Isha", "offset": 115, "duration": 60, "color": C_RED},
}

# --- EXCLUSIONS ---
FRIDAY_EXCLUSIONS = [
    "Mutoon Memorization", "Quran Memorization", "Quran Testing", 
    "Work Session 1", "Work Session 2", "Work Session 3", 
    "Business Development"
]
WEEKEND_EXCLUSIONS = ["Work Session 3"]

def get_prayer_times():
    today = arrow.now()
    url = f"http://api.aladhan.com/v1/calendarByCity?city={CITY}&country={COUNTRY}&method={METHOD}&month={today.month}&year={today.year}"
    return requests.get(url).json()['data']

def cleanup_calendar(service):
    print("🧹 Starting Cleanup...")
    past = arrow.now('Africa/Cairo').shift(days=-5).isoformat()
    future = arrow.now('Africa/Cairo').shift(days=30).isoformat()
    page_token = None
    while True:
        events_result = service.events().list(
            calendarId=CALENDAR_ID, timeMin=past, timeMax=future, 
            singleEvents=True, pageToken=page_token
        ).execute()
        for event in events_result.get('items', []):
            if event.get('summary', '') in TASKS_TO_CLEAN or 'Productivity Bot' in event.get('description', ''):
                try:
                    service.events().delete(calendarId=CALENDAR_ID, eventId=event['id']).execute()
                    time.sleep(0.5)
                except Exception: pass
        page_token = events_result.get('nextPageToken')
        if not page_token: break
    print("✅ Cleanup Complete.")

def main():
    if not SERVICE_ACCOUNT_JSON: return
    creds = service_account.Credentials.from_service_account_info(
        json.loads(SERVICE_ACCOUNT_JSON), scopes=['https://www.googleapis.com/auth/calendar']
    )
    service = build('calendar', 'v3', credentials=creds)

    cleanup_calendar(service)
    prayer_data = get_prayer_times()

    for day_data in prayer_data:
        date_str = day_data['date']['readable']
        timings = day_data['timings']
        for p in timings: timings[p] = timings[p].split(' ')[0]

        today_date = arrow.get(date_str, "DD MMM YYYY", tzinfo='Africa/Cairo')
        if today_date < arrow.now('Africa/Cairo').shift(days=-1): continue

        is_friday = today_date.weekday() == 4
        is_weekend = today_date.weekday() in [5, 6]

        anchors = {
            "Fajr": arrow.get(f"{date_str} {timings['Fajr']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Dhuhr": arrow.get(f"{date_str} {timings['Dhuhr']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Asr": arrow.get(f"{date_str} {timings['Asr']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Maghrib": arrow.get(f"{date_str} {timings['Maghrib']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Isha": arrow.get(f"{date_str} {timings['Isha']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
        }

        # --- 1. COLLECT EVENTS ---
        daily_events = [] 

        def schedule(summary, start, end, color):
            daily_events.append({'summary': summary, 'start': start, 'end': end, 'colorId': color})

        # Routine Copy
        current_routine = routine.copy()
        
        # Weekend Adjustments
        if is_weekend:
            current_routine["Islamic Reading"] = {"anchor": "Dhuhr", "offset": 115, "duration": 60, "color": C_PEACOCK}
            current_routine["Mutoon Memorization"] = {"anchor": "Fajr", "offset": 60, "duration": 30, "color": C_PEACOCK}
            current_routine["Work Session 1"] = {"anchor": "Fajr", "offset": 95, "duration": 120, "color": C_RED}
            current_routine["Business Development"] = {"anchor": "Fajr", "offset": 220, "duration": 60, "color": C_RED}
            current_routine["Work Session 2"] = {"anchor": "Fajr", "offset": 285, "duration": 120, "color": C_RED}

        # Special Flows
        if is_friday:
            schedule("Jumu'ah Prayer", anchors["Dhuhr"], anchors["Dhuhr"].shift(minutes=60), C_GREEN)
            
            c_start = arrow.get(f"{date_str} 08:00", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo')
            c_end = arrow.get(f"{date_str} 10:00", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo')
            schedule("Commute to Class", c_start.shift(hours=-1), c_start, C_GREEN)
            schedule("Class (Weekly)", c_start, c_end, C_GREEN)
            schedule("Commute Home", c_end, c_end.shift(hours=1), C_GREEN)
            
            b_start = c_end.shift(hours=1)
            schedule("Business Development", b_start, b_start.shift(minutes=60), C_RED)
            
            w1_start = anchors["Dhuhr"].shift(minutes=75)
            schedule("Friday Work Session 1", w1_start, w1_start.shift(minutes=60), C_RED)
            w2_start = anchors["Isha"].shift(minutes=50)
            schedule("Friday Work Session 2", w2_start, w2_start.shift(minutes=180), C_RED)

        if is_weekend:
            c_start = anchors["Isha"].shift(minutes=15)
            schedule("Commute to Class", c_start.shift(minutes=-60), c_start, C_GREEN)
            schedule("Class (Weekly)", c_start, c_start.shift(minutes=120), C_GREEN)
            schedule("Commute Home", c_start.shift(minutes=120), c_start.shift(minutes=180), C_GREEN)

        # Process Standard Routine
        for task_name, rules in current_routine.items():
            if is_friday and task_name in FRIDAY_EXCLUSIONS: continue
            if is_weekend and task_name in WEEKEND_EXCLUSIONS: continue
            if is_friday and task_name == "Dhuhr Prayer": continue

            anchor_time = anchors.get(rules['anchor'])
            if anchor_time:
                start_time = anchor_time.shift(minutes=rules['offset'])
                end_time = start_time.shift(minutes=rules['duration'])
                schedule(task_name, start_time, end_time, rules['color'])

        # --- 2. AUTO-TRIM LOGIC ---
        daily_events.sort(key=lambda x: x['start'])

        for i in range(len(daily_events) - 1):
            current = daily_events[i]
            next_ev = daily_events[i+1]
            
            # If overlap, cut current
            if current['end'] > next_ev['start']:
                # Ensure we don't accidentally cut if they just touch
                overlap = (current['end'] - next_ev['start']).seconds
                if overlap > 0:
                    current['end'] = next_ev['start']

        # --- 3. PUSH TO GOOGLE ---
        for ev in daily_events:
            duration_mins = (ev['end'] - ev['start']).seconds / 60
            if duration_mins < 5: continue # Skip if trimmed to < 5 mins

            final_event = {
                'summary': ev['summary'],
                'start': {'dateTime': ev['start'].isoformat(), 'timeZone': 'Africa/Cairo'},
                'end': {'dateTime': ev['end'].isoformat(), 'timeZone': 'Africa/Cairo'},
                'description': 'Productivity Bot (Auto-Trimmed)',
                'colorId': ev['colorId']
            }
            try:
                service.events().insert(calendarId=CALENDAR_ID, body=final_event).execute()
                print(f"Added {ev['summary']}")
            except Exception: pass

if __name__ == "__main__":
    main()
