import pandas as pd
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import io
import base64
import os
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed # Import these

app = Flask(__loader__) # Use __loader__ instead of __file__ for Flask in Cloud Run, though __name__ works too

# --- New Root Route for Debugging ---
@app.route('/')
def hello_root():
    print("DEBUG: Root / endpoint hit!")
    return "Hello, root is working!", 200
# --- End New Root Route ---

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
        # Use requests.Session() for persistent connections if making many requests to the same host
        # For simplicity here, sticking to direct requests.get as it's already in fetch_available_slots.
        # If you were making hundreds of requests to the same base URL, a Session would be more efficient.
        response = requests.get(url, params=params, headers=headers, timeout=10) # Add timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Error fetching data for {location} on {date_str}: {e}") # Changed to ERROR
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
        print("DEBUG: Starting generate_report function.")
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

        # --- Concurrent Fetching ---
        # Data collection dictionaries
        # Initialize as empty to be populated by concurrent tasks
        expo_weekday_data = {}
        sims_weekday_data = {}
        expo_weekend_data = {}
        sims_weekend_data = {}

        tasks = []
        # Max workers should ideally be related to the number of concurrent requests you expect/allow.
        # For 14 requests, 5-10 workers is usually a good starting point for I/O-bound tasks.
        # More workers isn't always better due to overhead.
        with ThreadPoolExecutor(max_workers=8) as executor: # You can adjust max_workers
            # Schedule weekday tasks
            for day in weekdays_dates:
                print(f"DEBUG: Scheduling weekday data fetch for {day}...")
                tasks.append(executor.submit(fetch_available_slots, day, "expo", WEEKDAY_TIMES))
                tasks.append(executor.submit(fetch_available_slots, day, "sims", WEEKDAY_TIMES))
            
            # Schedule weekend tasks
            for day in weekends_dates:
                print(f"DEBUG: Scheduling weekend data fetch for {day}...")
                tasks.append(executor.submit(fetch_available_slots, day, "expo", WEEKEND_TIMES))
                tasks.append(executor.submit(fetch_available_slots, day, "sims", WEEKEND_TIMES))

            # Collect results as they complete
            for future in as_completed(tasks):
                try:
                    result_data = future.result()
                    # The result_data is just the court_list from fetch_available_slots
                    # We need to know which date/location it belongs to.
                    # This requires modifying fetch_available_slots to return more context,
                    # or creating a wrapper function.
                    # For simplicity and to minimize changes to fetch_available_slots,
                    # let's map the results back based on the original task parameters.
                    # This is slightly less elegant but works by reconstructing intent.
                    # A better way would be to return (date_str, location, court_list) from fetch_available_slots.
                    
                    # Alternative: Pass all required info into fetch_available_slots, and it returns it along with data
                    # Let's adjust fetch_available_slots to return (date_str, location, allowed_times, court_list)
                    # And then process that. This is cleaner.
                    pass # Placeholder for now, will modify fetch_available_slots too

                except Exception as exc:
                    print(f"ERROR: A fetch task generated an exception: {exc}")
        
        # Re-organize data collection to work with concurrent results
        # We need to map the futures back to their original requests.
        # A better approach: a function that runs the fetches and directly populates the data.

        # Let's modify fetch_available_slots to return the context too.
        # It's better for it to return (date_str, location, results)
        
        # ---- Revised Strategy for Concurrent Data Collection ----
        all_results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_params = {}
            
            for day in weekdays_dates:
                future_to_params[executor.submit(fetch_available_slots, day, "expo", WEEKDAY_TIMES)] = (day, "expo", "weekday")
                future_to_params[executor.submit(fetch_available_slots, day, "sims", WEEKDAY_TIMES)] = (day, "sims", "weekday")
            
            for day in weekends_dates:
                future_to_params[executor.submit(fetch_available_slots, day, "expo", WEEKEND_TIMES)] = (day, "expo", "weekend")
                future_to_params[executor.submit(fetch_available_slots, day, "sims", WEEKEND_TIMES)] = (day, "sims", "weekend")

            for future in as_completed(future_to_params):
                date_str, location, day_type = future_to_params[future]
                try:
                    courts_data = future.result() # This is the {court: [times]} dictionary
                    if day_type == "weekday":
                        if location == "expo":
                            expo_weekday_data[date_str] = courts_data
                        else: # sims
                            sims_weekday_data[date_str] = courts_data
                    else: # weekend
                        if location == "expo":
                            expo_weekend_data[date_str] = courts_data
                        else: # sims
                            sims_weekend_data[date_str] = courts_data
                except Exception as exc:
                    print(f"ERROR: Fetching for {location} on {date_str} generated an exception: {exc}")
                    # Decide how to handle errors, e.g., populate with empty data
                    if day_type == "weekday":
                        if location == "expo":
                            expo_weekday_data[date_str] = {}
                        else: # sims
                            sims_weekday_data[date_str] = {}
                    else: # weekend
                        if location == "expo":
                            expo_weekend_data[date_str] = {}
                        else: # sims
                            sims_weekend_data[date_str] = {}


        # --- Format Output Message (NO CHANGES FROM PREVIOUS STEP) ---
        output_parts = []

        output_parts.append("🏸 Badminton Court Availability (Next 7 Days) 🏸")
        # output_parts.append(f"*(Data as of {datetime.now().strftime('%d %b %Y, %I:%M %p %Z')})*\n") # Keep commented out
        
        # Weekday Report
        output_parts.append("\n--- Weekdays (7 PM - 11 PM) ---")
        
        output_parts.append("\n🏟️ Expo Courts:")
        # Sort by date for consistent output order
        for date_str in sorted(expo_weekday_data.keys()):
            courts_data = expo_weekday_data[date_str] # Get data for this date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"✅ {formatted_date} : {' | '.join(sorted_times)}")
            else:
                output_parts.append(f"❌ {formatted_date}: No timeslots found.")
        
        output_parts.append("\n🏟️ Sims Courts:")
        # Sort by date for consistent output order
        for date_str in sorted(sims_weekday_data.keys()):
            courts_data = sims_weekday_data[date_str] # Get data for this date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"✅ {formatted_date} : {' | '.join(sorted_times)}")
            else:
                output_parts.append(f"❌ {formatted_date}: No timeslots found.")


        # Weekend Report
        output_parts.append("\n--- Weekends (11 AM - 10 PM) ---")

        output_parts.append("\n🏟️ Expo Courts:")
        # Sort by date for consistent output order
        for date_str in sorted(expo_weekend_data.keys()):
            courts_data = expo_weekend_data[date_str] # Get data for this date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"✅ {formatted_date} : {' | '.join(sorted_times)}")
            else:
                output_parts.append(f"❌ {formatted_date}: No timeslots found.")
        
        output_parts.append("\n🏟️ Sims Courts:")
        # Sort by date for consistent output order
        for date_str in sorted(sims_weekend_data.keys()):
            courts_data = sims_weekend_data[date_str] # Get data for this date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
            unique_times = set()
            for times in courts_data.values():
                unique_times.update(times)
            sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

            if unique_times:
                output_parts.append(f"✅ {formatted_date} : {' | '.join(sorted_times)}")
            else:
                output_parts.append(f"❌ {formatted_date}: No timeslots found.")

        final_message = "\n".join(output_parts)
        
        img_base64 = None 

        print("DEBUG: generate_report completed successfully.")
        return {
            "message": final_message,
            "image": img_base64 
        }

    except Exception as e:
        import traceback
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
    print(f"DEBUG: Returning result from /execute: {result.get('message')[:50]}...")
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"DEBUG: Flask app starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)



# import pandas as pd
# from bs4 import BeautifulSoup
# import requests
# from datetime import datetime
# import io
# import base64
# # import matplotlib.pyplot as plt # <--- KEEP THIS LINE COMMENTED OUT FOR NOW
# import os
# from flask import Flask, request, jsonify

# app = Flask(__name__)

# # --- New Root Route for Debugging ---
# @app.route('/')
# def hello_root():
#     print("DEBUG: Root / endpoint hit!")
#     return "Hello, root is working!", 200
# # --- End New Root Route ---

# # Constants
# WEEKDAY_TIMES = ["07:00 PM", "08:00 PM", "09:00 PM", "10:00 PM", "11:00 PM"]
# WEEKEND_TIMES = ["11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM", "08:00 PM", "09:00 PM", "10:00 PM"]

# # Court definitions
# EXPO_COURTS = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10', 'B11', 'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21', 'B22']
# SIMS_COURTS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

# FACILITY_IDS = {
#     "expo": "2967",
#     "sims": "2965"
# }
# LOCATION_COURTS = {
#     "expo": EXPO_COURTS,
#     "sims": SIMS_COURTS
# }

# def fetch_available_slots(date_str, location, allowed_times):
#     """Fetches available slots for a given date, location, and list of times."""
#     url = "https://singaporebadmintonhall.getomnify.com/welcome/loadSlotsByTagId"
    
#     if location not in FACILITY_IDS:
#         return {} # Return empty if unknown location

#     params = {
#         "date": date_str,
#         "facilitytag_id": FACILITY_IDS[location],
#         "timezone": "Asia/Singapore"
#     }
#     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"} # Good practice to use a real UA
    
#     try:
#         response = requests.get(url, params=params, headers=headers, timeout=10) # Add timeout
#         response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
#     except requests.exceptions.RequestException as e:
#         print(f"ERROR: Error fetching data for {location} on {date_str}: {e}") # Changed to ERROR
#         return {}

#     soup = BeautifulSoup(response.text, 'html.parser')
#     slots = soup.select('div.time-slot.facility-slot')

#     court_list = {}
#     for slot in slots:
#         court = slot.get("data-facility_name")
#         time = slot.get("data-starttime")
#         is_blocked = slot.get("data-isBlocked") == "1"
#         blocked_class = "blockedslot" in slot.get("class", [])
#         is_available = not (is_blocked or blocked_class)

#         if court in LOCATION_COURTS[location] and time in allowed_times and is_available:
#             court_list.setdefault(court, []).append(time)
            
#     return court_list

# def generate_report():
#     """
#     Main function to generate the availability report.
#     Returns a dictionary with 'message' and optionally 'image' (base64).
#     """
#     try:
#         print("DEBUG: Starting generate_report function.")
#         today = datetime.today().date()
#         weekdays_dates = []
#         weekends_dates = []

#         for i in range(1, 8):
#             the_date = today + pd.Timedelta(days=i)
#             date_str = the_date.strftime('%Y-%m-%d')
#             if the_date.weekday() >= 5: # 5 is Saturday, 6 is Sunday
#                 weekends_dates.append(date_str)
#             else:
#                 weekdays_dates.append(date_str)

#         # Data collection dictionaries
#         expo_weekday_data = {}
#         sims_weekday_data = {}
#         expo_weekend_data = {}
#         sims_weekend_data = {}

#         # Fetch weekday data
#         for day in weekdays_dates:
#             print(f"DEBUG: Fetching weekday data for {day}...")
#             expo_weekday_data[day] = fetch_available_slots(day, "expo", WEEKDAY_TIMES)
#             sims_weekday_data[day] = fetch_available_slots(day, "sims", WEEKDAY_TIMES)

#         # Fetch weekend data
#         for day in weekends_dates:
#             print(f"DEBUG: Fetching weekend data for {day}...")
#             expo_weekend_data[day] = fetch_available_slots(day, "expo", WEEKEND_TIMES)
#             sims_weekend_data[day] = fetch_available_slots(day, "sims", WEEKEND_TIMES)

#         # --- Format Output Message ---
#         output_parts = []

#         output_parts.append("🏸 **Badminton Court Availability (Next 7 Days)** 🏸\n")
#         # output_parts.append(f"*(Data as of {datetime.now().strftime('%d %b %Y, %I:%M %p %Z')})*\n") # Keep commented out
        
#         # Weekday Report
#         output_parts.append("\n--- **Weekdays (7 PM - 11 PM)** ---\n")
        
#         output_parts.append("\n**Expo Courts:**")
#         for date_str, courts_data in expo_weekday_data.items():
#             date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#             formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
#             unique_times = set()
#             for times in courts_data.values():
#                 unique_times.update(times)
#             sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

#             if unique_times:
#                 output_parts.append(f"\n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
#             else:
#                 output_parts.append(f"\n❌ **{formatted_date}**: No timeslots found.")
        
#         output_parts.append("\n**Sims Courts:**")
#         for date_str, courts_data in sims_weekday_data.items():
#             date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#             formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
#             unique_times = set()
#             for times in courts_data.values():
#                 unique_times.update(times)
#             sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

#             if unique_times:
#                 output_parts.append(f"\n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
#             else:
#                 output_parts.append(f"\n❌ **{formatted_date}**: No timeslots found.")


#         # Weekend Report
#         output_parts.append("\n--- **Weekends (11 AM - 10 PM)** ---\n")

#         output_parts.append("\n**Expo Courts:**")
#         for date_str, courts_data in expo_weekend_data.items():
#             date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#             formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
#             unique_times = set()
#             for times in courts_data.values():
#                 unique_times.update(times)
#             sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

#             if unique_times:
#                 output_parts.append(f"\n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
#             else:
#                 output_parts.append(f"\n❌ **{formatted_date}**: No timeslots found.")
        
#         output_parts.append("\n**Sims Courts:**")
#         for date_str, courts_data in sims_weekend_data.items():
#             date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#             formatted_date = date_obj.strftime("%d %b %Y (%a)")
            
#             unique_times = set()
#             for times in courts_data.values():
#                 unique_times.update(times)
#             sorted_times = sorted(list(unique_times), key=lambda t: datetime.strptime(t, "%I:%M %p"))

#             if unique_times:
#                 output_parts.append(f"\n✅ **{formatted_date}**: Available timeslots: {', '.join(sorted_times)}")
#             else:
#                 output_parts.append(f"\n❌ **{formatted_date}**: No timeslots found.")

#         final_message = "\n".join(output_parts)
        
#         img_base64 = None 

#         print("DEBUG: generate_report completed successfully.")
#         return {
#             "message": final_message,
#             "image": img_base64 
#         }

#     except Exception as e:
#         import traceback
#         print(f"ERROR: Unhandled exception in generate_report: {traceback.format_exc()}") 
#         return {
#             "message": f"An unexpected error occurred: {str(e)}\n\nPlease check the logs in Cloud Run.",
#             "image": None
#         }

# # --- Flask Endpoint ---
# @app.route('/execute', methods=['POST'])
# def handle_execute():
#     """
#     API endpoint that receives requests from Google Apps Script.
#     """
#     print("DEBUG: /execute endpoint hit.")
#     result = generate_report()
#     print(f"DEBUG: Returning result from /execute: {result.get('message')[:50]}...")
#     return jsonify(result)

# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 8080))
#     print(f"DEBUG: Flask app starting on port {port}")
#     app.run(host='0.0.0.0', port=port, debug=True)
