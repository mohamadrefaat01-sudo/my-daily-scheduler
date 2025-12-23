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

# --- CLEANUP LIST (Includes ALL versions we created) ---
TASKS_TO_CLEAN = [
    "Mutoon Memorization", "Business Development", 
    "Deep Work Session 1", "Deep Work Session 2", 
    "Work Session 1", "Work Session 2", "Work Session 3",
    "Power Nap (Qailulah)", "Quran Memorization", "Quran Testing",
    "Exercise / Gym", "Islamic Reading",
    "Fajr Prayer", "Dhuhr Prayer", "Asr Prayer", "Maghrib Prayer", "Isha Prayer"
]

# --- THE OPTIMIZED ROUTINE ---
routine = {
    # --- PRAYERS ---
    "Fajr Prayer":   {"anchor": "Fajr", "offset": 0, "duration": 20},
    "Dhuhr Prayer":  {"anchor": "Dhuhr", "offset": 0, "duration": 20},
    "Asr Prayer":    {"anchor": "Asr", "offset": 0, "duration": 20},
    "Maghrib Prayer":{"anchor": "Maghrib", "offset": 0, "duration": 20},
    "Isha Prayer":   {"anchor": "Isha", "offset": 0, "duration": 20},

    # --- MORNING BLOCK ---
    "Mutoon Memorization": {"anchor": "Fajr", "offset": 30, "duration": 30},
    
    # 1. Work Session 1 (High Focus) - Starts 1h 10m after Fajr
    "Work Session 1": {"anchor": "Fajr", "offset": 70, "duration": 90}, 
    
    # 2. Business - Starts after Work 1 + break
    "Business Development": {"anchor": "Fajr", "offset": 170, "duration": 60},
    
    # 3. Work Session 2 (Before Nap)
    "Work Session 2": {"anchor": "Fajr", "offset": 240, "duration": 90}, 

    # --- MID-DAY ---
    "Power Nap (Qailulah)": {"anchor": "Dhuhr", "offset": -45, "duration": 20},
    "Quran Memorization": {"anchor": "Dhuhr", "offset": 25, "duration": 60}, 

    # --- AFTERNOON ---
    "Quran Testing": {"anchor": "Asr", "offset": 25, "duration": 15},
    "Exercise / Gym": {"anchor": "Maghrib", "offset": -90, "duration": 60},
    
    # --- EVENING ---
    "Islamic Reading": {"anchor": "Maghrib", "offset": 30, "duration": 60},
    
    # 4. Night Work (Capped at 1h)
    "Work Session 3": {"anchor": "Isha", "offset": 30, "duration": 60},
}

FRIDAY_EXCLUSIONS = ["Mutoon Memorization", "Quran Memorization", "Quran Testing", "Work Session 1", "Work Session 2", "Work Session 3"]

def get_prayer_times():
    today = arrow.now()
    url = f"http://api.aladhan.com/v1/calendarByCity?city={CITY}&country={COUNTRY}&method={METHOD}&month={today.month}&year={today.year}"
    return requests.get(url).json()['data']

def cleanup_calendar(service):
    """Deletes ALL bot events using Pagination to find every single one."""
    print("🧹 Starting Deep Cleanup... Scanning all pages...")
    
    # Look back 5 days to be safe, and forward 30 days
    past = arrow.now('Africa/Cairo').shift(days=-5).isoformat()
    future = arrow.now('Africa/Cairo').shift(days=30).isoformat()
    
    page_token = None
    total_deleted = 0

    while True:
        # Fetch a page of events
        events_result = service.events().list(
            calendarId=CALENDAR_ID, 
            timeMin=past, 
            timeMax=future, 
            singleEvents=True,
            pageToken=page_token  # This is the key fix
        ).execute()
        
        events = events_result.get('items', [])

        for event in events:
            summary = event.get('summary', '')
            description = event.get('description', '')
            
            # Check if this is a bot event
            if summary in TASKS_TO_CLEAN or 'Productivity Bot' in description:
                try:
                    service.events().delete(calendarId=CALENDAR_ID, eventId=event['id']).execute()
                    print(f"Deleted: {summary} ({event['start'].get('dateTime')})")
                    total_deleted += 1
                except Exception as e:
                    print(f"Could not delete {summary}: {e}")
        
        # Check if there is another page of results
        page_token = events_result.get('nextPageToken')
        if not page_token:
            break
    
    print(f"✅ Cleanup Complete. Removed {total_deleted} events.")

def main():
    if not SERVICE_ACCOUNT_JSON:
        print("Error: No Google Key found!")
        return

    creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=['https://www.googleapis.com/auth/calendar']
    )
    service = build('calendar', 'v3', credentials=creds)

    # 1. RUN DEEP CLEANUP
    cleanup_calendar(service)

    # 2. CREATE NEW SCHEDULE
    print("Fetching Prayer Times...")
    prayer_data = get_prayer_times()

    for day_data in prayer_data:
        date_str = day_data['date']['readable']
        timings = day_data['timings']
        for prayer in timings: timings[prayer] = timings[prayer].split(' ')[0]

        today_date = arrow.get(date_str, "DD MMM YYYY", tzinfo='Africa/Cairo')
        
        # Only schedule from TODAY onwards
        if today_date < arrow.now('Africa/Cairo').shift(days=-1): continue

        is_friday = today_date.weekday() == 4
        
        anchors = {
            "Fajr": arrow.get(f"{date_str} {timings['Fajr']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Dhuhr": arrow.get(f"{date_str} {timings['Dhuhr']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Asr": arrow.get(f"{date_str} {timings['Asr']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Maghrib": arrow.get(f"{date_str} {timings['Maghrib']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
            "Isha": arrow.get(f"{date_str} {timings['Isha']}", "DD MMM YYYY HH:mm", tzinfo='Africa/Cairo'),
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
