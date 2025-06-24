# app.py (for Google Cloud Run deployment)

import pandas as pd
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import io
import base64
import matplotlib.pyplot as plt
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Constants
WEEKDAY_TIMES = ["07:00 PM", "08:00 PM", "09:00 PM", "10:00 PM", "11:00 PM"]
WEEKEND_TIMES = ["11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM", "08:00 PM", "09:00 PM", "10:00 PM"]

# Court definitions
EXPO_COURTS = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10', 'B11', 'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21', 'B22']
SIMS_COURTS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

FACILITY_IDS = {
    "expo": "2967",
    "sims": "2965"
}
LOCATION_COURTS = {
    "expo": EXPO_COURTS,
    "sims": SIMS_COURTS
}

def fetch_available_slots(date_str, location, allowed_times):
    """Fetches available slots for a given date, location, and list of times."""
    url = "https://singaporebadmintonhall.getomnify.com/welcome/loadSlotsByTagId"
    
    if location not in FACILITY_IDS:
        return {} # Return empty if unknown location

    params = {
        "date": date_str,
        "facilitytag_id": FACILITY_IDS[location],
        "timezone": "Asia/Singapore"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"} # Good practice to use a real UA
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10) # Add timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {location} on {date_str}: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    slots = soup.select('div.time-slot.facility-slot')

    court_list = {}
    for slot in slots:
        court = slot.get("data-facility_name")
        time = slot.get("data-starttime")
        is_blocked = slot.get("data-isBlocked") == "1"
        blocked_class = "blockedslot" in slot.get("class", [])
        is_available = not (is_blocked or blocked_class)

        if court in LOCATION_COURTS[location] and time in allowed_times and is_available:
            court_list.setdefault(court, []).append(time)
            
    return court_list

def generate_report():
    """
    Main function to generate the availability report.
    Returns a dictionary with 'message' and optionally 'image' (base64).
    """
    try:
        today = datetime.today().date()
        weekdays_dates = []
        weekends_dates = []

        for i in range(1, 8):
            the_date = today + pd.Timedelta(days=i)
            date_str = the_date.strftime('%Y-%m-%d')
            if the_date.weekday() >= 5: # 5 is Saturday, 6 is Sunday
                weekends_dates.append(date_str)
            else:
                weekdays_dates.append(date_str)

        # Data collection dictionaries
        expo_weekday_data = {}
        sims_weekday_data = {}
        expo_weekend_data = {}
        sims_weekend_data = {}

        # Fetch weekday data
        for day in weekdays_dates:
            expo_weekday_data[day] = fetch_available_slots(day, "expo", WEEKDAY_TIMES)
            sims_weekday_data[day] = fetch_available_slots(day, "sims", WEEKDAY_TIMES)

        # Fetch weekend data
        for day in weekends_dates:
            expo_weekend_data[day] = fetch_available_slots(day, "expo", WEEKEND_TIMES)
            sims_weekend_data[day] = fetch_available_slots(day, "sims", WEEKEND_TIMES)

        # --- Format Output Message ---
        output_parts = []

        output_parts.append("🏸 **Badminton Court Availability (Next 7 Days)** 🏸n")
        output_parts.append(f"*(Data as of {datetime.now().strftime('%d %b %Y, %I:%M %p %Z')})*n")

        # Weekday Report
        output_parts.append("n--- **Weekdays (7 PM - 11 PM)** ---n")
        
        output_parts.append("n**Expo Courts:**")
        for date_str, courts_data in expo_weekday_data.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
                # For brevity, only print courts with multiple timeslots or if specific info is needed
                # for court, times in sorted(courts_data.items()):
                #     if times: output_parts.append(f"  {court}: {', '.join(times)}")
            else:
                output_parts.append(f"n❌ **{formatted_date}**: No timeslots found.")
        
        output_parts.append("n**Sims Courts:**")
        for date_str, courts_data in sims_weekday_data.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
            else:
                output_parts.append(f"n❌ **{formatted_date}**: No timeslots found.")


        # Weekend Report
        output_parts.append("n--- **Weekends (11 AM - 10 PM)** ---n")

        output_parts.append("n**Expo Courts:**")
        for date_str, courts_data in expo_weekend_data.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
            else:
                output_parts.append(f"n❌ **{formatted_date}**: No timeslots found.")
        
        output_parts.append("n**Sims Courts:**")
        for date_str, courts_data in sims_weekend_data.items():
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
            else:
                output_parts.append(f"n❌ **{formatted_date}**: No timeslots found.")

        final_message = "n".join(output_parts)
        
        # You could generate a summary plot here if desired, e.g.,
        # total available slots per day/location, etc.
        # For simplicity, I'm omitting plot generation for this specific script,
        # but the structure is there if you want to add it.
        img_base64 = None 

        return {
            "message": final_message,
            "image": img_base64 # This will be None unless you add plot generation
        }

    except Exception as e:
        import traceback
        print(f"Error in generate_report: {traceback.format_exc()}")
        return {
            "message": f"An unexpected error occurred: {str(e)}nnPlease check the logs.",
            "image": None
        }

# --- Flask Endpoint ---
@app.route('/execute', methods=['POST'])
def handle_execute():
    """
    API endpoint that receives requests from Google Apps Script.
    This specific script doesn't need input parameters, so the request body
    can be empty or ignored.
    """
    # You can ignore the request.get_json() if no input is needed
    # data = request.get_json() 
    
    result = generate_report() # Call your main logic function
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)