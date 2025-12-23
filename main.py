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
# 10=Green(Basil), 11=Red(Tomato), 7=Peacock(Turquoise), 8=Grey(Graphite)
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
    "Friday Work Session 1", "Friday Work Session 2"
]

# --- THE DAILY ROUTINE ---
routine = {
    # --- PRAYERS (Calculated Durations: Athan + Pray + Athkar) ---
    # Fajr: 25 wait + 15 pray + 15 athkar = 55 mins
    "Fajr Prayer":   {"anchor": "Fajr", "offset": 0, "duration": 55, "color": C_GREEN},
    
    # Dhuhr: 20 wait + 15 pray + 10 athkar = 45 mins
    "Dhuhr Prayer":  {"anchor": "Dhuhr", "offset": 0, "duration": 45, "color": C_GREEN},
    
    # Asr: 20 wait + 15 pray + 10 athkar = 45 mins
    "Asr Prayer":    {"anchor": "Asr", "offset": 0, "duration": 45, "color": C_GREEN},
    
    # Maghrib: 12 wait + 15 pray + 15 athkar = 42 mins
    "Maghrib Prayer":{"anchor": "Maghrib", "offset": 0, "duration": 42, "color": C_GREEN},
    
    # Isha: 20 wait + 15 pray + 10 athkar = 45 mins
    "Isha Prayer":   {"anchor": "Isha", "offset": 0, "duration": 45, "color": C_GREEN},

    # --- TASKS (Offsets shifted to accommodate longer prayers) ---
    
    # Mutoon: Starts after Fajr (Offset 60 mins)
    "Mutoon Memorization": {"anchor": "Fajr", "offset": 60, "duration": 30, "color": C_PEACOCK},
    
    # Work 1: Starts after Mutoon (Offset 95 mins)
    "Work Session 1": {"anchor": "Fajr", "offset": 95, "duration": 90, "color": C_RED}, 
    
    # Business: Starts after Work 1 (Offset 190 mins)
    "Business Development": {"anchor": "Fajr", "offset": 190, "duration": 60, "color": C_RED},
    
    # Work 2: Starts after Business (Offset 255 mins)
    "Work Session 2": {"anchor": "Fajr", "offset": 255, "duration": 90, "color": C_RED}, 
    
    # Mid-Day
    "Power Nap (Qailulah)": {"anchor": "Dhuhr", "offset": -45, "duration": 20, "color": C_GREEN},
    
    # Quran Memo: Starts 50 mins after Dhuhr (Allows for 45m prayer block + 5m buffer)
    "Quran Memorization": {"anchor": "Dhuhr", "offset": 50, "duration": 60, "color": C_PEACOCK}, 
    
    # Reading: Gap Filler
    "Islamic Reading": {"anchor": "Dhuhr", "offset": 115, "duration": 60, "color": C_PEACOCK},

    # Afternoon
    # Testing: Starts 50 mins after Asr (Allows for 45m prayer block)
    "Quran Testing": {"anchor": "Asr", "offset": 50, "duration": 15, "color": C_PEACOCK},
    "Exercise / Gym": {"anchor": "Maghrib", "offset": -90, "duration": 60, "color": C_GREY},
    
    # Night Work: Starts 50 mins after Isha (Allows for 45m prayer block)
    "Work Session 3": {"anchor": "Isha", "offset": 50, "duration": 60, "color": C_RED},
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
        
        events = events_result.get('items', [])
        for event in events:
            summary = event.get('summary', '')
            description = event.get('description', '')
            if summary in TASKS_TO_CLEAN or 'Productivity Bot' in description:
                try:
                    service.events().delete(calendarId=CALENDAR_ID, eventId=event['id']).execute()
                    time.sleep(0.5) 
                except Exception:
                    pass
        
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

        # --- DYNAMIC ROUTINE ADJUSTMENTS ---
        current_routine = routine.copy()
        
        # WEEKEND COMPRESSION (Sat/Sun)
        if is_weekend:
            # Shift everything to fit after the 55-min Fajr
            # Mutoon: Fajr + 60 (same as weekday)
            current_routine["Mutoon Memorization"] = {"anchor": "Fajr", "offset": 60, "duration": 30, "color": C_PEACOCK}
            
            # Work 1: Starts Fajr + 95 (same start) -> Duration 120 (2h)
            current_routine["Work Session 1"] = {"anchor": "Fajr", "offset": 95, "duration": 120, "color": C_RED}
            
            # Biz: Starts Fajr + 220
            current_routine["Business Development"] = {"anchor": "Fajr", "offset": 220, "duration": 60, "color": C_RED}
            
            # Work 2: Starts Fajr + 285 -> Duration 120 (2h)
            # End = Fajr + 405 mins. (approx 6.75 hours after Fajr). 
            # If Fajr is 5:20, End is ~12:05 PM. 
            # Note: This might bump into Dhuhr in winter. On weekends, if it overlaps Dhuhr slightly, prioritize prayer.
            current_routine["Work Session 2"] = {"anchor": "Fajr", "offset": 285, "duration": 120, "color": C_RED}

        # --- SPECIAL FLOWS ---
        
        if is_friday:
            # Jumu'ah (Green) - 60 mins
            create_event(service, "Jumu'ah Prayer", anchors["Dhuhr"], anchors["Dhuhr"].shift(minutes=60), C_GREEN)
            
            # Class Logic
            class_start = arrow.get(f"{date_str} 08:00", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo')
            class_end = arrow.get(f"{date_str} 10:00", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo')
            create_event(service, "Commute to Class", class_start.shift(hours=-1), class_start, C_GREEN)
            create_event(service, "Class (Weekly)", class_start, class_end, C_GREEN)
            create_event(service, "Commute Home", class_end, class_end.shift(hours=1), C_GREEN)
            
            # Biz
            biz_start = class_end.shift(hours=1)
            create_event(service, "Business Development", biz_start, biz_start.shift(minutes=60), C_RED)
            
            # Work 1 (1h) - Starts after Jumu'ah block
            work_fri_1_start = anchors["Dhuhr"].shift(minutes=75)
            create_event(service, "Friday Work Session 1", work_fri_1_start, work_fri_1_start.shift(minutes=60), C_RED)
            
            # Work 2 (3h) - Starts after Isha block (Isha + 50)
            work_fri_2_start = anchors["Isha"].shift(minutes=50)
            create_event(service, "Friday Work Session 2", work_fri_2_start, work_fri_2_start.shift(minutes=180), C_RED)

        if is_weekend:
            # Class Logic
            commute_start = anchors["Maghrib"].shift(minutes=20)
            create_event(service, "Commute to Class", commute_start, commute_start.shift(minutes=60), C_GREEN)
            
            class_start = anchors["Isha"].shift(minutes=20) # Slightly more buffer after Isha
            class_end = class_start.shift(minutes=120)
            create_event(service, "Class (Weekly)", class_start, class_end, C_GREEN)
            create_event(service, "Commute Home", class_end, class_end.shift(minutes=60), C_GREEN)

        # --- STANDARD ROUTINE LOOP ---
        for task_name, rules in current_routine.items():
            if is_friday and task_name in FRIDAY_EXCLUSIONS: continue
            if is_weekend and task_name in WEEKEND_EXCLUSIONS: continue
            if is_friday and task_name == "Dhuhr Prayer": continue

            anchor_time = anchors.get(rules['anchor'])
            if anchor_time:
                start_time = anchor_time.shift(minutes=rules['offset'])
                end_time = start_time.shift(minutes=rules['duration'])
                create_event(service, task_name, start_time, end_time, rules['color'])

def create_event(service, summary, start, end, color_id):
    event = {
        'summary': summary,
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Africa/Cairo'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Africa/Cairo'},
        'description': 'Productivity Bot',
        'colorId': color_id
    }
    try:
        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        print(f"Added {summary}")
    except Exception:
        pass

if __name__ == "__main__":
    main()
