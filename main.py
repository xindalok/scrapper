import pandas as pd
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import os
from flask import Flask, request, jsonify
import traceback # For better error logging

app = Flask(__name__) 

# --- Flask Root Route for Health Checks/Debugging ---
@app.route('/')
def hello_root():
    print("DEBUG: Root / endpoint hit!")
    return "Hello, root is working!", 200

# --- Constants ---
WEEKDAY_TIMES = ["07:00 PM", "08:00 PM", "09:00 PM", "10:00 PM"]
WEEKEND_TIMES = ["11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM", "08:00 PM", "09:00 PM", "10:00 PM"]

# Consolidated Court definitions
EXPO_COURTS = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10', 'B11', 'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21', 'B22']
EXPO_COURTS_A = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10']
EXPO_COURTS_B = ['B11', 'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21', 'B22']

SIMS_COURTS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]
SIMS_COURTS_P = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"]
SIMS_COURTS_D = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

FACILITY_IDS = {
    "expo": "2967",
    "sims": "2965"
}

LOCATION_COURTS_ALL = {
    "expo": EXPO_COURTS,
    "sims": SIMS_COURTS
}

def fetch_available_slots(date_str, location, allowed_times):
    """
    Fetches available slots for a given date, location, and list of times.
    Returns (date_str, location, allowed_times, court_list) for consistency.
    """
    url = "https://singaporebadmintonhall.getomnify.com/welcome/loadSlotsByTagId"
    
    if location not in FACILITY_IDS:
        print(f"ERROR: Unknown location: {location}")
        return date_str, location, allowed_times, {}

    params = {
        "date": date_str,
        "facilitytag_id": FACILITY_IDS[location],
        "timezone": "Asia/Singapore"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Error fetching data for {location} on {date_str}: {e}")
        return date_str, location, allowed_times, {}

    soup = BeautifulSoup(response.text, 'html.parser')
    slots = soup.select('div.time-slot.facility-slot')

    court_list = {}
    for slot in slots:
        court = slot.get("data-facility_name")
        time = slot.get("data-starttime")
        is_blocked = slot.get("data-isBlocked") == "1"
        blocked_class = "blockedslot" in slot.get("class", [])
        is_available = not (is_blocked or blocked_class)

        if court in LOCATION_COURTS_ALL[location] and time in allowed_times and is_available:
            court_list.setdefault(court, []).append(time)
            
    return date_str, location, allowed_times, court_list

def generate_report():
    """
    Main function to generate the availability report, with detailed court breakdown.
    Now uses sequential fetching without ThreadPoolExecutor.
    """
    try:
        print("DEBUG: Starting generate_report function (sequential fetching).")
        today = datetime.today().date()
        weekdays_dates = []
        weekends_dates = []

        for i in range(1, 8):
            the_date = today + pd.Timedelta(days=i)
            date_str = the_date.strftime('%Y-%m-%d')
            if the_date.weekday() >= 5:
                weekends_dates.append(date_str)
            else:
                weekdays_dates.append(date_str)

        all_fetched_data = {
            "expo_weekday": {},
            "sims_weekday": {},
            "expo_weekend": {},
            "sims_weekend": {}
        }

        # --- Sequential Fetching (ThreadPoolExecutor removed) ---
        # Fetch weekday data
        for day_str in weekdays_dates:
            print(f"DEBUG: Fetching weekday data for {day_str} (Expo)...")
            _, _, _, courts_data = fetch_available_slots(day_str, "expo", WEEKDAY_TIMES)
            all_fetched_data["expo_weekday"][day_str] = courts_data

            print(f"DEBUG: Fetching weekday data for {day_str} (Sims)...")
            _, _, _, courts_data = fetch_available_slots(day_str, "sims", WEEKDAY_TIMES)
            all_fetched_data["sims_weekday"][day_str] = courts_data
        
        # Fetch weekend data
        for day_str in weekends_dates:
            print(f"DEBUG: Fetching weekend data for {day_str} (Expo)...")
            _, _, _, courts_data = fetch_available_slots(day_str, "expo", WEEKEND_TIMES)
            all_fetched_data["expo_weekend"][day_str] = courts_data

            print(f"DEBUG: Fetching weekend data for {day_str} (Sims)...")
            _, _, _, courts_data = fetch_available_slots(day_str, "sims", WEEKEND_TIMES)
            all_fetched_data["sims_weekend"][day_str] = courts_data


        # --- Format Output Message ---
        output_parts = []

        output_parts.append("🏸 Badminton Court Availability (Next 7 Days) 🏸\n\n\n")
        
        # --- Weekday Report ---
        output_parts.append("━━━━━━━━━━━━━━━")
        output_parts.append("    WEEKDAYS    ")  # 4 spaces each side
        output_parts.append("  (7 PM – 10 PM) ")
        output_parts.append("━━━━━━━━━━━━━━━")


        
        # Expo Courts for Weekdays
        output_parts.append("\n🏟️🏟️ Expo 🏟️🏟️") 
        for date_str in sorted(all_fetched_data["expo_weekday"].keys()):
            courts_data = all_fetched_data["expo_weekday"][date_str]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b (%a)") 
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            
            if len(unique_times) > 1: # More than one unique time
                output_parts.append(f"\n📅 {formatted_date}") 
                for court in sorted(courts_data.keys()):
                    times_for_court = sorted(courts_data[court], key=lambda t: datetime.strptime(t, "%I:%M %p"))
                    if times_for_court: # Only print court if it has times
                        output_parts.append(f"  🩵 {court} - {' | '.join(times_for_court)}") # Added orange circle
            elif len(unique_times) == 1: # Exactly one unique time
                output_parts.append(f"\n❌ {formatted_date}: Insufficient slots for proper booking")
            else: # No unique times (len == 0)
                output_parts.append(f"\n❌ {formatted_date}: No timeslots found.")
        
        # Sims Courts for Weekdays
        output_parts.append("\n🏟️🏟️ Sims 🏟️🏟️") 
        for date_str in sorted(all_fetched_data["sims_weekday"].keys()):
            courts_data = all_fetched_data["sims_weekday"][date_str]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            
            if len(unique_times) > 1: # More than one unique time
                output_parts.append(f"\n📅 {formatted_date}") 
                for court in sorted(courts_data.keys()):
                    times_for_court = sorted(courts_data[court], key=lambda t: datetime.strptime(t, "%I:%M %p"))
                    if times_for_court: # Only print court if it has times
                        output_parts.append(f"  💙 {court} - {' | '.join(times_for_court)}") # Added orange circle
            elif len(unique_times) == 1: # Exactly one unique time
                output_parts.append(f"\n❌ {formatted_date}: Insufficient slots for proper booking")
            else: # No unique times (len == 0)
                output_parts.append(f"\n❌ {formatted_date}: No timeslots found.")


        # --- Weekend Report ---
        output_parts.append(f"\n{'='*15}")
        output_parts.append("━━━━━━━━━━━━━━━")
        output_parts.append("    WEEKENDS    ")  # 4 spaces each side
        output_parts.append("  (11 AM – 10 PM) ")
        output_parts.append("━━━━━━━━━━━━━━━")


        # Expo Courts for Weekends (with A/B breakdown)
        output_parts.append("\n🏟️🏟️ Expo 🏟️🏟️") 
        for date_str in sorted(all_fetched_data["expo_weekend"].keys()):
            courts_data = all_fetched_data["expo_weekend"][date_str]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b (%a)")
            
            unique_times_all = set()
            for times in courts_data.values():
                unique_times_all.update(times)
            
            if len(unique_times_all) > 1: # More than one unique time
                output_parts.append(f"\n📅 {formatted_date}") 
                
                court_a_data = {k: v for k, v in courts_data.items() if k in EXPO_COURTS_A}
                court_b_data = {k: v for k, v in courts_data.items() if k in EXPO_COURTS_B}

                if court_a_data:
                    output_parts.append("  --------------------") 
                    for court in sorted(court_a_data.keys()):
                        times = sorted(court_a_data[court], key=lambda t: datetime.strptime(t, "%I:%M %p"))
                        if times:
                            output_parts.append(f"    🟠 {court} - {' | '.join(times)}") # Added orange circle
                
                if court_b_data:
                    output_parts.append("  --------------------") 
                    for court in sorted(court_b_data.keys()):
                        times = sorted(court_b_data[court], key=lambda t: datetime.strptime(t, "%I:%M %p"))
                        if times:
                            output_parts.append(f"    🔵 {court} - {' | '.join(times)}") # Added orange circle
            elif len(unique_times_all) == 1: # Exactly one unique time
                output_parts.append(f"\n❌ {formatted_date}: Insufficient slots for proper booking")
            else: # No unique times (len == 0)
                output_parts.append(f"\n❌ {formatted_date}: No timeslots found.")
        
        # Sims Courts for Weekends (with P/D breakdown)
        output_parts.append("\n🏟️🏟️ Sims 🏟️🏟️") 
        for date_str in sorted(all_fetched_data["sims_weekend"].keys()):
            courts_data = all_fetched_data["sims_weekend"][date_str]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b (%a)")
            
            unique_times_all = set()
            for times in courts_data.values():
                unique_times_all.update(times)
            
            if len(unique_times_all) > 1: # More than one unique time
                output_parts.append(f"\n📅 {formatted_date}") 
                
                court_p_data = {k: v for k, v in courts_data.items() if k in SIMS_COURTS_P}
                court_d_data = {k: v for k, v in courts_data.items() if k in SIMS_COURTS_D}

                if court_p_data:
                    output_parts.append("  --------------------") 
                    for court in sorted(court_p_data.keys()):
                        times = sorted(court_p_data[court], key=lambda t: datetime.strptime(t, "%I:%M %p"))
                        if times:
                            output_parts.append(f"    🟡 {court} - {' | '.join(times)}") # Added orange circle
                
                if court_d_data:
                    output_parts.append("  --------------------") 
                    for court in sorted(court_d_data.keys()):
                        times = sorted(court_d_data[court], key=lambda t: datetime.strptime(t, "%I:%M %p"))
                        if times:
                            output_parts.append(f"    🟤 {court} - {' | '.join(times)}") # Added orange circle
            elif len(unique_times_all) == 1: # Exactly one unique time
                output_parts.append(f"\n❌ {formatted_date}: Insufficient slots for proper booking")
            else: # No unique times (len == 0)
                output_parts.append(f"\n❌ {formatted_date}: No timeslots found.")

        final_message = "\n".join(output_parts)
        
        img_base64 = None 

        print("DEBUG: generate_report completed successfully.")
        return {
            "message": final_message,
            "image": img_base64 
        }

    except Exception as e:
        print(f"ERROR: Unhandled exception in generate_report: {traceback.format_exc()}") 
        return {
            "message": f"An unexpected error occurred: {str(e)}\n\nPlease check the logs in Cloud Run.",
            "image": None
        }

# --- Flask Endpoint ---
@app.route('/execute', methods=['POST'])
def handle_execute():
    """
    API endpoint that receives requests from Google Apps Script.
    """
    print("DEBUG: /execute endpoint hit.")
    result = generate_report()
    print(f"DEBUG: Returning result from /execute: {result.get('message')[:100]}...")
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"DEBUG: Flask app starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
