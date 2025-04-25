import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, time
import logging
import json
import re
from dateutil.parser import parse as dateutil_parse
from typing import Dict, List, Any, Optional, Tuple, Union
from dotenv import load_dotenv
import time as sleep_time
import random
import threading
import platform
import time
import calendar

# Import notification services
from services.notification_service import (
    schedule_reminders,
    notify_barber_of_booking,
    send_booking_confirmation,
    notify_barber_of_cancellation,
    notify_barber_of_reschedule
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for Google Sheets setup
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
CREDS_FILE = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID')

logger.info(f"Using Google Sheet ID: {SHEET_ID}")
logger.info(f"Credentials file path: {os.path.abspath(CREDS_FILE) if CREDS_FILE else 'Not set'}")

# Constants for the barber shop
OPENING_HOUR = 10  # 10 AM
CLOSING_HOUR = 18  # 6 PM
APPOINTMENT_DURATION = 30  # 30 minutes
WORKING_DAYS = [0, 1, 2, 3, 4, 5]  # Monday to Saturday (0 = Monday in our setup)

# Mock database for development - in production, use Google Sheets
# This is a fallback in case Google Sheets integration isn't set up
MOCK_DB = {
    "appointments": [],
    "customers": {}  # Store customer data including names
}

# FORCE_MOCK_DB set to True to always use mock data 
FORCE_MOCK_DB = False

# Force current date to the real current system date 
real_now = datetime.now()
FORCE_CURRENT_DATE = real_now
logger.info(f"Setting forced current date to real system date: {FORCE_CURRENT_DATE}")
logger.info(f"System time details: {time.ctime()}")
logger.info(f"System platform: {platform.system()}, Python: {platform.python_version()}")
logger.info(f"Current year: {real_now.year}, month: {real_now.month}, day: {real_now.day}")

# Helper function to get current date/time consistently
def get_current_datetime():
    """Get the current datetime, with option to override for testing."""
    # Always use the real current time, not a forced time
    # This ensures dates are calculated correctly for appointments
    current = datetime.now()
    logger.debug(f"Current datetime: {current}")
    return current

# Add some mock sample data for testing
def initialize_mock_data():
    """Initialize some mock data for testing"""
    MOCK_DB["appointments"] = []
    
    # Add a couple of appointments for the next few days
    for day_offset in range(1, 4):
        next_day = get_current_datetime() + timedelta(days=day_offset)
        # Skip Sundays
        if next_day.weekday() == 6:  # Sunday
            continue
            
        # Add an appointment at 11:00 AM
        morning_appt = {
            'id': f'APPT-{int(get_current_datetime().timestamp())}-{day_offset}-1',
            'phone': '+19176565597',
            'datetime': next_day.replace(hour=11, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S"),
            'service_type': 'haircut',
            'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
        }
        MOCK_DB["appointments"].append(morning_appt)
        
        # Add an appointment at 2:00 PM
        afternoon_appt = {
            'id': f'APPT-{int(get_current_datetime().timestamp())}-{day_offset}-2',
            'phone': '+19176565597',
            'datetime': next_day.replace(hour=14, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S"),
            'service_type': 'haircut',
            'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
        }
        MOCK_DB["appointments"].append(afternoon_appt)

# Initialize mock data
initialize_mock_data()

# Rate limiter class for Google Sheets API
class RateLimiter:
    def __init__(self, max_calls_per_minute=60):
        self.max_calls = max_calls_per_minute
        self.calls = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if we've exceeded the rate limit"""
        with self.lock:
            now = get_current_datetime()
            # Remove calls older than 1 minute
            self.calls = [t for t in self.calls if now - t < timedelta(minutes=1)]
            
            # If we've hit the limit, wait
            if len(self.calls) >= self.max_calls:
                oldest_call = self.calls[0]
                sleep_seconds = 60 - (now - oldest_call).total_seconds()
                sleep_seconds = max(0, sleep_seconds) + random.random()  # Add jitter
                
                if sleep_seconds > 0:
                    logger.warning(f"Rate limit reached. Waiting {sleep_seconds:.2f} seconds.")
                    # Release the lock while sleeping
                    self.lock.release()
                    try:
                        sleep_time.sleep(sleep_seconds)
                    finally:
                        self.lock.acquire()
            
            # Add this call to the list
            self.calls.append(now)

# Create a global rate limiter
sheets_rate_limiter = RateLimiter(max_calls_per_minute=50)  # Conservative limit

# Decorate functions that use Google Sheets API
def rate_limited(func):
    def wrapper(*args, **kwargs):
        sheets_rate_limiter.wait_if_needed()
        return func(*args, **kwargs)
    return wrapper

def get_sheet_client():
    """Get Google Sheets client or None if credentials not available."""
    if FORCE_MOCK_DB:
        logger.info("FORCE_MOCK_DB is enabled, using mock database")
        return None
        
    tries = 0
    max_tries = 5
    
    while tries < max_tries:
        try:
            # If we have credentials file, use Google Sheets
            creds_path = os.path.abspath(CREDS_FILE) if CREDS_FILE else None
            logger.info(f"Looking for credentials file at: {creds_path}")
            logger.info(f"Google Sheet ID: {SHEET_ID}")
            
            if os.path.exists(CREDS_FILE) and SHEET_ID:
                logger.info(f"Credentials file found, attempting to connect to Google Sheets")
                creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPES)
                client = gspread.authorize(creds)
                
                # Try opening the sheet to verify connection
                try:
                    sheet = client.open_by_key(SHEET_ID)
                    worksheets = sheet.worksheets()
                    logger.info(f"Successfully connected to Google Sheet. Worksheets: {[ws.title for ws in worksheets]}")
                    
                    # Check if Appointments worksheet exists
                    appointments_ws = None
                    for ws in worksheets:
                        if ws.title == "Appointments":
                            appointments_ws = ws
                            break
                    
                    if not appointments_ws:
                        logger.warning(f"No 'Appointments' worksheet found. Available worksheets: {[ws.title for ws in worksheets]}")
                        # Create the Appointments worksheet with headers
                        logger.info("Creating 'Appointments' worksheet with headers")
                        appointments_ws = sheet.add_worksheet(title="Appointments", rows=100, cols=20)
                        appointments_ws.append_row(['id', 'phone', 'datetime', 'service_type', 'created_at'])
                        logger.info("'Appointments' worksheet created successfully")
                    else:
                        logger.info(f"Found existing 'Appointments' worksheet with {appointments_ws.row_count} rows")
                        # Check if the worksheet has headers
                        try:
                            headers = appointments_ws.row_values(1)
                            logger.info(f"Current worksheet headers: {headers}")
                            if not headers or len(headers) < 5:
                                logger.warning("Worksheet headers missing or incomplete, resetting headers")
                                appointments_ws.clear()
                                appointments_ws.append_row(['id', 'phone', 'datetime', 'service_type', 'created_at'])
                        except Exception as header_error:
                            logger.error(f"Error checking worksheet headers: {header_error}")
                    
                    return client
                except gspread.exceptions.APIError as api_error:
                    if hasattr(api_error, 'response') and api_error.response.status_code == 429:
                        # Rate limit exceeded, implement exponential backoff
                        tries += 1
                        wait_time = (2 ** tries) + random.random()
                        logger.warning(f"Rate limit exceeded. Attempt {tries}/{max_tries}. Waiting {wait_time:.2f} seconds...")
                        sleep_time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"API Error accessing Google Sheet: {api_error}")
                        return None
                except Exception as sheet_error:
                    logger.error(f"Error accessing Google Sheet: {sheet_error}")
                    return None
            else:
                if not os.path.exists(CREDS_FILE):
                    logger.warning(f"Credentials file not found at: {os.path.abspath(CREDS_FILE) if CREDS_FILE else 'Not set'}")
                if not SHEET_ID:
                    logger.warning("Google Sheet ID not found in environment variables")
                logger.warning("Google Sheets credentials not found, using mock database")
                return None
        except Exception as e:
            logger.error(f"Error connecting to Google Sheets: {e}")
            return None
        
        # If we get here and we're still in the loop, we need to try again
        tries += 1
        wait_time = (2 ** tries) + random.random()
        logger.warning(f"General error. Attempt {tries}/{max_tries}. Waiting {wait_time:.2f} seconds...")
        sleep_time.sleep(wait_time)
    
    # If we've exhausted all retries
    logger.error("Max retries reached for Google Sheets connection. Using mock database.")
    return None

def parse_date_time(date_str: str, time_str: str) -> Optional[datetime]:
    """Parse date and time strings into a datetime object."""
    try:
        # Handle special cases first
        date_str = date_str.lower().strip()
        time_str = time_str.lower().strip()
        
        # Handle "tomorrow"
        if date_str == "tomorrow":
            base_date = get_current_datetime().date() + timedelta(days=1)
        else:
            # Try to parse date_str directly
            try:
                parsed_date = dateutil_parse(date_str, fuzzy=True).date()
                base_date = parsed_date
            except:
                logger.error(f"Error parsing date: {date_str}")
                return None
        
        # For time, check if it's in format like "3pm" or "3:30pm" or "15:00"
        time_pattern = r'(\d+)(?::(\d+))?\s*(am|pm)?'
        time_match = re.match(time_pattern, time_str, re.IGNORECASE)
        
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            
            # Handle am/pm
            am_pm = time_match.group(3)
            if am_pm:
                if am_pm.lower() == 'pm' and hour < 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0
            
            # Combine date and time
            return datetime(
                year=base_date.year,
                month=base_date.month,
                day=base_date.day,
                hour=hour,
                minute=minute
            )
        else:
            # Try parsing the time string
            try:
                parsed_time = dateutil_parse(time_str, fuzzy=True).time()
                return datetime.combine(base_date, parsed_time)
            except:
                logger.error(f"Error parsing time: {time_str}")
                return None
    
    except Exception as e:
        logger.error(f"Error parsing date/time: {e}, date_str={date_str}, time_str={time_str}")
        return None

def is_valid_appointment_time(dt: datetime) -> bool:
    """Check if the appointment time is valid (during business hours and working days)."""
    # Check if day is a working day
    if dt.weekday() not in WORKING_DAYS:
        return False
    
    # Check if time is during business hours
    if dt.hour < OPENING_HOUR or dt.hour >= CLOSING_HOUR:
        return False
    
    # Check if it's at least 1 hour in the future
    if dt < get_current_datetime() + timedelta(hours=1):
        return False
    
    # Check if it's a valid time slot (every 30 minutes)
    if dt.minute not in [0, 30]:
        return False
    
    return True

def get_available_slots(date: str, service_type: str = "haircut") -> List[str]:
    """Get available time slots for a given date."""
    try:
        # Log the real current date/time at call time for debugging
        real_now = datetime.now()
        logger.info(f"Real current datetime at call time: {real_now}")
        logger.info(f"Using current datetime from get_current_datetime(): {get_current_datetime()}")
        logger.info(f"Getting available slots for date: '{date}' and service_type: '{service_type}'")
        
        # First try to handle it as a YYYY-MM-DD string
        try:
            date_parts = date.split('-')
            if len(date_parts) == 3:
                year, month, day = map(int, date_parts)
                target_date = datetime(year=year, month=month, day=day)
                logger.info(f"Parsed as ISO format date: {target_date}")
            else:
                # Not in ISO format, use dateutil parser
                target_date = dateutil_parse(date, fuzzy=True)
                logger.info(f"Parsed with dateutil: {target_date}")
        except Exception as e:
            logger.error(f"Error parsing date string '{date}': {e}")
            # Try with dateutil as a fallback
            try:
                target_date = dateutil_parse(date, fuzzy=True)
                logger.info(f"Fallback parse with dateutil: {target_date}")
            except:
                logger.error(f"Could not parse date '{date}' at all")
                return []
                
        target_date = datetime(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day
        )
        
        logger.info(f"Using target date: {target_date}")
        
        # Check if it's a working day
        if target_date.weekday() not in WORKING_DAYS:
            logger.info(f"Date {target_date} is not a working day (weekday={target_date.weekday()})")
            return []
        
        # Generate all possible slots
        all_slots = []
        for hour in range(OPENING_HOUR, CLOSING_HOUR):
            for minute in [0, 30]:
                slot_time = datetime(
                    year=target_date.year,
                    month=target_date.month,
                    day=target_date.day,
                    hour=hour, 
                    minute=minute
                )
                # Add all future slots (more than 1 hour away)
                # For dates beyond today, include all slots
                if target_date.date() > get_current_datetime().date() or slot_time > get_current_datetime() + timedelta(hours=1):
                    all_slots.append(slot_time)
        
        logger.info(f"Generated {len(all_slots)} possible slots for {target_date}")
        
        # Get existing appointments for that day
        existing_appointments = get_appointments_for_date(target_date)
        logger.info(f"Found {len(existing_appointments)} existing appointments for {target_date}")
        
        # If no appointments found in the future, just return all slots
        # Added extra check for future dates
        if not existing_appointments:
            logger.info(f"No existing appointments found, all slots are available")
            return [slot.strftime("%I:%M %p") for slot in all_slots]
        
        # Filter out booked slots
        available_slots = []
        for slot in all_slots:
            is_available = True
            for appt in existing_appointments:
                try:
                    appt_time = dateutil_parse(appt['datetime'])
                    # Check if this slot overlaps with an existing appointment
                    if abs((slot - appt_time).total_seconds()) < (APPOINTMENT_DURATION * 60):
                        is_available = False
                        logger.info(f"Slot {slot} conflicts with appointment at {appt_time}")
                        break
                except Exception as e:
                    logger.error(f"Error comparing appointment times: {e}")
                    continue
            
            if is_available:
                available_slots.append(slot.strftime("%I:%M %p"))
        
        logger.info(f"Found {len(available_slots)} available slots")
        for slot in available_slots:
            logger.debug(f"Available slot: {slot}")
        return available_slots
    
    except Exception as e:
        logger.error(f"Error getting available slots: {e}")
        return []

@rate_limited
def get_appointments_for_date(target_date: datetime) -> List[Dict[str, Any]]:
    """Get all appointments for a specific date."""
    client = get_sheet_client()
    
    if client:
        # Real implementation with Google Sheets
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet("Appointments")
            all_records = sheet.get_all_records()
            
            # Filter to only get appointments for the target date
            return [
                record for record in all_records 
                if dateutil_parse(record['datetime']).date() == target_date.date()
            ]
        except Exception as e:
            logger.error(f"Error getting appointments from sheet: {e}")
            return []
    else:
        # Mock implementation
        target_date_str = target_date.strftime("%Y-%m-%d")
        return [
            appt for appt in MOCK_DB["appointments"] 
            if appt['datetime'].startswith(target_date_str)
        ]

@rate_limited
def get_appointments_for_phone(phone_number: str) -> List[Dict[str, Any]]:
    """Get all appointments for a specific phone number."""
    client = get_sheet_client()
    
    if client:
        # Real implementation with Google Sheets
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet("Appointments")
            all_records = sheet.get_all_records()
            
            # Filter to only get appointments for this phone number
            return [
                record for record in all_records 
                if record['phone'] == phone_number
            ]
        except Exception as e:
            logger.error(f"Error getting appointments from sheet: {e}")
            return []
    else:
        # Mock implementation
        return [
            appt for appt in MOCK_DB["appointments"] 
            if appt['phone'] == phone_number
        ]

@rate_limited
def add_appointment_to_sheet(appointment: Dict[str, Any]) -> bool:
    """Add a new appointment to the Google Sheet."""
    client = get_sheet_client()
    
    if client:
        try:
            logger.info(f"Getting worksheet 'Appointments' from sheet ID: {SHEET_ID}")
            sheet = client.open_by_key(SHEET_ID).worksheet("Appointments")
            
            # Verify the sheet exists and has correct headers
            try:
                headers = sheet.row_values(1)
                logger.info(f"Current sheet headers: {headers}")
                
                if not headers or len(headers) < 7:  # Need 7 columns now including customer_name
                    logger.warning("Sheet headers missing or incomplete, adding headers")
                    sheet.clear()
                    sheet.append_row(['id', 'phone', 'datetime', 'service_type', 'recipient', 'customer_name', 'created_at'])
            except Exception as e:
                logger.error(f"Error checking headers: {e}, attempting to add headers")
                sheet.clear()
                sheet.append_row(['id', 'phone', 'datetime', 'service_type', 'recipient', 'customer_name', 'created_at'])
            
            # Add the new appointment
            sheet.append_row([
                appointment['id'],
                appointment['phone'],
                appointment['datetime'],
                appointment['service_type'],
                appointment.get('recipient', 'self'),  # Add recipient, default to self if not specified
                appointment.get('customer_name', ''),  # Add customer name
                appointment['created_at']
            ])
            logger.info(f"Added appointment {appointment['id']} to sheet")
            return True
        except Exception as e:
            logger.error(f"Error adding appointment to sheet: {e}")
            return False
    else:
        # Mock implementation
        logger.info(f"Using mock database for booking - client was not available")
        MOCK_DB["appointments"].append(appointment)
        return True

@rate_limited
def remove_appointment_from_sheet(appointment_id: str) -> bool:
    """Remove an appointment from Google Sheets."""
    client = get_sheet_client()
    
    if client:
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet("Appointments")
            all_records = sheet.get_all_records()
            
            # Find the row index for this appointment
            row_idx = None
            for i, record in enumerate(all_records, 2):  # Start at 2 because row 1 is headers
                if record['id'] == appointment_id:
                    row_idx = i
                    break
            
            if row_idx:
                sheet.delete_row(row_idx)
                logger.info(f"Removed appointment {appointment_id} from sheet")
                return True
            else:
                logger.warning(f"Appointment {appointment_id} not found in sheet")
                return False
        except Exception as e:
            logger.error(f"Error removing appointment from sheet: {e}")
            return False
    else:
        # Mock implementation
        for i, appt in enumerate(MOCK_DB["appointments"]):
            if appt['id'] == appointment_id:
                MOCK_DB["appointments"].pop(i)
                return True
        return False

@rate_limited
def update_appointment_in_sheet(appointment_id: str, new_data: Dict[str, Any]) -> bool:
    """Update an existing appointment in Google Sheets."""
    client = get_sheet_client()
    
    if client:
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet("Appointments")
            all_records = sheet.get_all_records()
            
            # Find the row index for this appointment
            row_idx = None
            for i, record in enumerate(all_records, 2):  # Start at 2 because row 1 is headers
                if record['id'] == appointment_id:
                    row_idx = i
                    break
            
            if row_idx:
                # Update the specific cells that have changed
                for key, value in new_data.items():
                    if key in ["phone", "datetime", "service_type"]:
                        col_idx = ["id", "phone", "datetime", "service_type", "created_at"].index(key) + 1
                        sheet.update_cell(row_idx, col_idx, value)
                
                logger.info(f"Updated appointment {appointment_id} in sheet")
                return True
            else:
                logger.warning(f"Appointment {appointment_id} not found in sheet")
                return False
        except Exception as e:
            logger.error(f"Error updating appointment in sheet: {e}")
            return False
    else:
        # Mock implementation
        for i, appt in enumerate(MOCK_DB["appointments"]):
            if appt['id'] == appointment_id:
                for key, value in new_data.items():
                    MOCK_DB["appointments"][i][key] = value
                return True
        return False

@rate_limited
def find_appointment(phone: str, appointment_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Find a specific appointment by ID or the next upcoming appointment for a phone number."""
    appointments = get_appointments_for_phone(phone)
    
    if not appointments:
        return None
        
    if appointment_id:
        # Find specific appointment by ID
        for appt in appointments:
            if appt['id'] == appointment_id:
                return appt
        return None
    else:
        # Find the next upcoming appointment
        upcoming = [appt for appt in appointments if dateutil_parse(appt['datetime']) > get_current_datetime()]
        if not upcoming:
            return None
            
        # Sort by date and return the earliest
        upcoming.sort(key=lambda x: dateutil_parse(x['datetime']))
        return upcoming[0]

def book_appointment(phone_number: str, entities: Dict) -> Dict:
    """Book a new appointment based on extracted entities."""
    logger.info(f"Booking appointment for {phone_number} with entities {entities}")
    
    try:
        # Extract entities
        date_time = entities.get('datetime')
        service_type = entities.get('service_type', 'haircut')
        is_confirmed = entities.get('confirmed', False)
        recipient = entities.get('recipient', 'self')  # Get recipient, default to 'self'
        customer_name = entities.get('customer_name', '')  # Get customer name if provided
        
        # If we have a customer name, store it in the customers database
        if customer_name:
            logger.info(f"Saving customer name: {customer_name} for {phone_number}")
            save_customer_info(phone_number, {"name": customer_name})
        else:
            # Try to get the customer's name from the database
            customer_info = get_customer_info(phone_number)
            if customer_info and customer_info.get('name'):
                customer_name = customer_info.get('name')
                logger.info(f"Retrieved customer name from database: {customer_name}")
        
        # Parse the date/time - check if it's already a formatted datetime string
        appointment_dt = None
        
        # First try to parse as an ISO formatted date string (YYYY-MM-DD HH:MM:SS)
        try:
            if isinstance(date_time, str) and " " in date_time and ":" in date_time:
                logger.info(f"Attempting to parse as ISO formatted string: {date_time}")
                appointment_dt = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
                logger.info(f"Successfully parsed as ISO format: {appointment_dt}")
            else:
                # Fall back to the natural language parser
                logger.info(f"Not an ISO format, using natural language parser")
                appointment_dt = parse_datetime(date_time)
        except Exception as parse_error:
            logger.error(f"Error parsing date string: {parse_error}")
            appointment_dt = parse_datetime(date_time)
            
        logger.info(f"Parsed date/time: '{date_time}' -> {appointment_dt}")
        
        if not appointment_dt:
            return {
                'success': False,
                'message': f"I couldn't understand that date and time. Please try something like 'tomorrow at 3pm', 'next Friday at 10:30am', or 'October 15th at 2pm'."
            }

        # Check if it's during business hours
        if not is_during_business_hours(appointment_dt):
            return {
                'success': False,
                'message': f"I'm sorry, but we're only open from {OPENING_HOUR}AM to {CLOSING_HOUR-12}PM, Monday through Saturday. Would you like to book at a different time?"
            }
            
        # Check if it's in the past
        if appointment_dt < get_current_datetime():
            logger.info(f"Requested time is in the past: {appointment_dt}. Current time: {get_current_datetime()}")
            return {
                'success': False,
                'message': "I can't book appointments in the past. Please choose a future date and time. How about tomorrow or later this week?"
            }
            
        # Format the date/time for a confirmation message if not confirmed yet
        formatted_time = appointment_dt.strftime('%A, %B %d at %I:%M %p')
        
        # Only check existing appointments for conflicts if booking for self
        skip_conflict_check = recipient.lower() != 'self'
        logger.info(f"Recipient is '{recipient}', skip_conflict_check = {skip_conflict_check}")
        
        if not is_confirmed:
            recipient_msg = "" if recipient.lower() == 'self' else f" for {recipient}"
            return {
                'success': False,
                'message': f"I'll book your {service_type} appointment{recipient_msg} for {formatted_time}. Is that correct? Please confirm to proceed with booking."
            }
        
        # Skip available slot check if booking for someone else
        if skip_conflict_check:
            logger.info(f"Skipping conflict check because booking for {recipient}")
        # Otherwise check if the slot is available
        elif not is_slot_available(appointment_dt):
            # Find nearby available slots
            day_str = appointment_dt.strftime("%Y-%m-%d")
            available_slots = get_available_slots(day_str)
            
            if available_slots:
                # Find closest available slots
                requested_minutes = appointment_dt.hour * 60 + appointment_dt.minute
                closest_slots = []
                
                for slot in available_slots[:3]:  # Get up to 3 alternatives
                    hour, minute = map(int, re.search(r"(\d+):(\d+)", slot).groups())
                    if "PM" in slot and hour != 12:
                        hour += 12
                    slot_minutes = hour * 60 + minute
                    closest_slots.append((abs(slot_minutes - requested_minutes), slot))
                
                closest_slots.sort()  # Sort by time difference
                alternative_times = ", ".join([slot for _, slot in closest_slots[:2]])
                
                return {
                    'success': False,
                    'message': f"I'm sorry, but that time slot is already booked. The closest available times on the same day are: {alternative_times}. Would you like to book one of these instead?"
                }
            else:
                # Check next day
                next_day = appointment_dt.date() + timedelta(days=1)
                # Skip to next working day if needed
                while next_day.weekday() not in WORKING_DAYS:
                    next_day += timedelta(days=1)
                    
                next_day_str = next_day.strftime("%Y-%m-%d")
                next_day_slots = get_available_slots(next_day_str)
                
                if next_day_slots:
                    formatted_date = next_day.strftime('%A, %B %d')
                    sample_times = ", ".join(next_day_slots[:3])
                    return {
                        'success': False,
                        'message': f"I'm sorry, but that time slot is already booked and we don't have any other openings on that day. We do have availability on {formatted_date}, including: {sample_times}. Would you like to book one of these instead?"
                    }
                else:
                    return {
                        'success': False,
                        'message': f"I'm sorry, but that time slot is already booked. We seem to be quite busy right now. Would you like to check availability for a different day?"
                    }
            
        # All checks passed, book the appointment
        appointment_id = book_appointment_slot(phone_number, appointment_dt, service_type, recipient)
        
        # Format the response time nicely
        formatted_time = appointment_dt.strftime('%A, %B %d at %I:%M %p')
        
        # Schedule reminders (now includes both 24h and 1h reminders)
        schedule_reminders(phone_number, appointment_dt)
        
        # Send confirmation to the customer
        send_booking_confirmation(phone_number, appointment_dt, service_type, appointment_id)
        
        # Notify the barber about the new booking
        barber_phone = os.environ.get('BARBER_PHONE_NUMBER', '+12345678901')
        barber_telegram = os.environ.get('BARBER_TELEGRAM_ID', None)
        
        logger.info(f"Sending notification to barber phone: {barber_phone}, barber Telegram: {barber_telegram}")
        notify_barber_of_booking(barber_phone, phone_number, appointment_dt, recipient)
        
        # Build a more conversational response based on the timing
        time_context = ""
        days_until = (appointment_dt.date() - get_current_datetime().date()).days
        
        if days_until == 0:
            time_context = "today"
        elif days_until == 1:
            time_context = "tomorrow"
        elif days_until < 7:
            time_context = f"this {appointment_dt.strftime('%A')}"
        
        recipient_msg = "" if recipient.lower() == 'self' else f" for {recipient}"
        
        return {
            'success': True,
            'appointment_id': appointment_id,
            'message': f"Perfect! I've booked your {service_type}{recipient_msg} for {formatted_time}. " + 
                      (f"See you {time_context}! " if time_context else "") +
                      f"You'll receive a reminder 24 hours and 1 hour before your appointment. Your confirmation number is #{appointment_id}. Is there anything else I can help you with?"
        }
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        return {
            'success': False,
            'message': "I apologize, but I encountered an issue while booking your appointment. Could you please try again with a specific date and time? For example, 'tomorrow at 2pm' or 'Friday at 10am'."
        }

def parse_datetime(datetime_str: str) -> Optional[datetime]:
    """Parse a natural language date and time expression."""
    try:
        # Log input for debugging
        logger.debug(f"Parsing datetime string: '{datetime_str}'")
        real_current_time = datetime.now()
        current_year = real_current_time.year
        current_month = real_current_time.month
        logger.debug(f"Real current time: {real_current_time} (Year: {current_year}, Month: {current_month})")
        
        # Handle special cases first
        datetime_str = datetime_str.lower()
        
        # Handle "tomorrow" directly
        if "tomorrow" in datetime_str:
            base_date = get_current_datetime().date() + timedelta(days=1)
            # Extract time part
            time_part = datetime_str.replace("tomorrow", "").strip()
            if "at" in time_part:
                time_part = time_part.split("at")[1].strip()
                
            # Parse time part
            if time_part:
                time_match = re.search(r"(\d+)(?::(\d+))?\s*(am|pm)?", time_part, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    am_pm = time_match.group(3)
                    
                    if am_pm and am_pm.lower() == "pm" and hour < 12:
                        hour += 12
                    elif am_pm and am_pm.lower() == "am" and hour == 12:
                        hour = 0
                    
                    result = datetime.combine(base_date, time(hour, minute))
                    logger.debug(f"Parsed 'tomorrow' with time: {result}")
                    return result
            
            # Default to noon if no valid time
            result = datetime.combine(base_date, time(12, 0))
            logger.debug(f"Parsed 'tomorrow', defaulted to noon: {result}")
            return result
            
        # Check for ISO format dates (YYYY-MM-DD)
        iso_match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', datetime_str)
        if iso_match:
            year = int(iso_match.group(1))
            month = int(iso_match.group(2))
            day = int(iso_match.group(3))
            
            # Extract time part
            time_part = re.sub(r'\d{4}-\d{1,2}-\d{1,2}', '', datetime_str).strip()
            if 'at' in time_part:
                time_part = time_part.split('at')[1].strip()
                
            if not time_part:
                # Default to noon if no time
                return datetime(year, month, day, 12, 0)
                
            # Try to parse time part
            time_match = re.search(r'(\d+)(?::(\d+))?\s*(am|pm)?', time_part, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                am_pm = time_match.group(3)
                
                if am_pm and am_pm.lower() == 'pm' and hour < 12:
                    hour += 12
                elif am_pm and am_pm.lower() == 'am' and hour == 12:
                    hour = 0
                    
                return datetime(year, month, day, hour, minute)
            else:
                # Default to noon
                return datetime(year, month, day, 12, 0)
                
        # For "day of week" like "Friday"
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if day in datetime_str.lower() or day[:3] in [word.lower() for word in datetime_str.split()]:
                # Important - use real current date for accurate day calculations
                now = datetime.now()
                current_year = now.year
                current_month = now.month
                logger.debug(f"Current date/time: {now} (Year: {current_year}, Month: {current_month})")
                today_weekday = now.weekday()  # 0 = Monday
                logger.debug(f"Today is weekday {today_weekday} ({days[today_weekday]})")
                days_ahead = (i - today_weekday) % 7
                
                # Check for "this" keyword to ensure we're looking at the correct week
                if "this" in datetime_str.lower():
                    # If days_ahead is large (like 5-6 days), it's still this week
                    logger.debug(f"'this' keyword found, ensuring we use current week")
                    # If we're already past that day this week, use next week
                    if days_ahead == 0 and now.hour >= CLOSING_HOUR:
                        days_ahead = 7
                        logger.debug(f"Today is {day} but after business hours, going to next week")
                
                # If days_ahead is 0, it means today - check if we should go to next week
                # If we're looking for the current day but it's already past business hours,
                # go to next week instead
                elif days_ahead == 0:
                    if now.hour >= CLOSING_HOUR:
                        days_ahead = 7
                        logger.debug(f"Today is {day} but after business hours, going to next week")
                # If days_ahead is small, it means this week - if today is Friday and target
                # is Sunday, days_ahead would be 2
                elif days_ahead < 7:
                    logger.debug(f"Next {day} is in {days_ahead} days")
                
                # Check for "next" keyword to push forward another week
                if "next" in datetime_str.lower():
                    # "Next Friday" means not this Friday, but the one after
                    if days_ahead < 7:
                        days_ahead += 7
                        logger.debug(f"'next' keyword found, adding 7 days")
                
                logger.debug(f"Day of week '{day}' (i={i}), today={today_weekday} ({days[today_weekday]}), days_ahead={days_ahead}")
                target_date = now.date() + timedelta(days=days_ahead)
                logger.debug(f"Calculated target_date: {target_date} (Year: {target_date.year}, Month: {target_date.month})")
                
                # Extract the time part by removing the day name and "next" if present
                time_parts = []
                for word in datetime_str.split():
                    word_lower = word.lower()
                    if (word_lower not in [day, day[:3], "next", "this", "on", "the"] and 
                        "at" not in word_lower and 
                        word_lower not in ["am", "pm"]):
                        time_parts.append(word)
                
                time_str = " ".join(time_parts).replace("at", "").strip()
                
                if ":" in time_str:
                    hour, minute = time_str.split(":")
                    hour = int(hour)
                    if "pm" in minute.lower() and hour < 12:
                        hour += 12
                    minute = int(minute.replace("am", "").replace("pm", "").strip())
                    result = datetime.combine(target_date, time(hour, minute))
                    logger.debug(f"Parsed time with colon: {result}")
                    return result
                elif time_str:
                    # Try to parse just the time
                    time_match = re.search(r"(\d+)\s*(am|pm)?", time_str)
                    if time_match:
                        hour = int(time_match.group(1))
                        am_pm = time_match.group(2)
                        
                        if am_pm and am_pm.lower() == "pm" and hour < 12:
                            hour += 12
                        elif am_pm and am_pm.lower() == "am" and hour == 12:
                            hour = 0
                        
                        result = datetime.combine(target_date, time(hour, 0))
                        logger.debug(f"Parsed time from regex: {result}")
                        return result
                    else:
                        # Default to noon
                        result = datetime.combine(target_date, time(12, 0))
                        logger.debug(f"No valid time format, defaulting to noon: {result}")
                        return result
                else:
                    # Default to noon if no time specified
                    result = datetime.combine(target_date, time(12, 0))
                    logger.debug(f"No time specified, defaulting to noon: {result}")
                    return result

        # Handle specific date patterns first (MM/DD/YYYY or DD/MM/YYYY)
        date_pattern = r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?'
        date_match = re.search(date_pattern, datetime_str)
        if date_match:
            # Got a date in format MM/DD or MM/DD/YY or similar
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else current_year
            
            # Fix 2-digit years
            if year < 100:
                year += 2000
            
            # Validate and adjust the date if needed
            if month > 12:
                # Swap month and day if month > 12 (assumes American format)
                month, day = day, month
            
            logger.debug(f"Parsed specific date pattern: year={year}, month={month}, day={day}")
            
            # Extract time
            time_part = re.sub(date_pattern, '', datetime_str).strip()
            time_obj = time(12, 0)  # Default to noon
            
            if time_part:
                time_match = re.search(r'(\d+)(?::(\d+))?\s*(am|pm)?', time_part, re.IGNORECASE)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    am_pm = time_match.group(3)
                    
                    if am_pm and am_pm.lower() == 'pm' and hour < 12:
                        hour += 12
                    elif am_pm and am_pm.lower() == 'am' and hour == 12:
                        hour = 0
                        
                    time_obj = time(hour, minute)
            
            try:
                now = datetime.now()
                parsed_dt = datetime(year, month, day, time_obj.hour, time_obj.minute)
                logger.debug(f"Created datetime from specific pattern: {parsed_dt}")
                
                # If it's in the past, move it to next month or year
                if parsed_dt < now and abs((parsed_dt - now).days) > 1:
                    # More than 1 day in the past, use next year
                    parsed_dt = parsed_dt.replace(year=current_year+1)
                    logger.debug(f"Date was in the past, moved to next year: {parsed_dt}")
                
                logger.debug(f"Final parsed result: {parsed_dt}")
                return parsed_dt
            except ValueError as e:
                logger.error(f"Invalid date from pattern: {e}")
                return None
                
        # If all direct parsing fails, try using the dateutil parser
        try:
            # Call dateutil_parse directly instead of using the parser module
            try:
                from dateutil.parser import parse
                parsed_dt = parse(datetime_str, fuzzy=True)
                logger.debug(f"dateutil parse result: {parsed_dt}, detected year: {parsed_dt.year}")
                
                now = datetime.now()
                # Always force current year if the parsed year is far in the future or past
                if abs(parsed_dt.year - current_year) > 1:
                    logger.debug(f"Year {parsed_dt.year} is far from current year {current_year}, forcing current year")
                    try:
                        parsed_dt = parsed_dt.replace(year=current_year)
                    except ValueError:
                        # Handle Feb 29 in leap years
                        if parsed_dt.month == 2 and parsed_dt.day == 29 and not (current_year % 4 == 0):
                            parsed_dt = parsed_dt.replace(month=2, day=28, year=current_year)
                        else:
                            logger.error(f"Error replacing year: {parsed_dt}")
                
                # Check for incorrect month detection
                if abs(parsed_dt.month - current_month) > 3:
                    # Fixed year but month is very different - likely wrong 
                    # The only exception is if we're near year boundaries
                    if not ((current_month == 12 and parsed_dt.month <= 2) or 
                            (current_month <= 2 and parsed_dt.month == 12)):
                        logger.debug(f"Month {parsed_dt.month} is far from current month {current_month}, forcing current month")
                        try:
                            # Calculate correct day for the month
                            max_day = [31, 29 if current_year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][current_month-1]
                            day = min(parsed_dt.day, max_day)
                            parsed_dt = parsed_dt.replace(month=current_month, day=day)
                        except ValueError as e:
                            logger.error(f"Error in month correction: {e}")
                
                # If the parser didn't extract a good time, default to noon
                if parsed_dt.hour == 0 and parsed_dt.minute == 0 and "am" not in datetime_str.lower() and "pm" not in datetime_str.lower():
                    parsed_dt = datetime.combine(parsed_dt.date(), time(12, 0))
                    logger.debug(f"No clear time found, defaulting to noon: {parsed_dt}")
                
                # If the date is in the past, move it to the future
                if parsed_dt < now:
                    if parsed_dt.month == now.month and parsed_dt.day == now.day:
                        # It's today but earlier time; use today but fix time
                        if parsed_dt.hour < now.hour or (parsed_dt.hour == now.hour and parsed_dt.minute < now.minute):
                            # Use tomorrow if it's past current time
                            fixed_date = (now + timedelta(days=1)).date()
                            parsed_dt = datetime.combine(fixed_date, parsed_dt.time())
                            logger.debug(f"Time is in the past today, moving to tomorrow: {parsed_dt}")
                    else:
                        # Past date - check if it's in this year but earlier months
                        if parsed_dt.year == current_year:
                            if parsed_dt.month < now.month or (parsed_dt.month == now.month and parsed_dt.day < now.day):
                                # Move to next month with same day
                                next_month = now.month + 1
                                next_year = current_year
                                if next_month > 12:
                                    next_month = 1
                                    next_year = current_year + 1
                                
                                try:
                                    parsed_dt = parsed_dt.replace(year=next_year, month=next_month)
                                    logger.debug(f"Date is in the past this year, moved to next month: {parsed_dt}")
                                except ValueError:
                                    # Handle month with fewer days
                                    last_day = [31, 29 if next_year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][next_month-1]
                                    parsed_dt = parsed_dt.replace(year=next_year, month=next_month, day=min(parsed_dt.day, last_day))
                                    logger.debug(f"Adjusted for month length: {parsed_dt}")
                
                logger.debug(f"Final parsed result: {parsed_dt} (Year: {parsed_dt.year}, Month: {parsed_dt.month}, Day: {parsed_dt.day})")
                return parsed_dt
            except ImportError:
                logger.error("Failed to import dateutil.parser.parse")
                return None
        except Exception as e:
            logger.error(f"Failed to parse with dateutil: {e}")
            return None
    
    except Exception as e:
        logger.error(f"Error parsing datetime: {e}, input: {datetime_str}")
        return None

def is_during_business_hours(dt: datetime) -> bool:
    """Check if the appointment time is during business hours."""
    return OPENING_HOUR <= dt.hour < CLOSING_HOUR

def is_slot_available(dt: datetime) -> bool:
    """Check if the appointment time slot is available."""
    # Check if it's a valid appointment time
    if not is_valid_appointment_time(dt):
        return False
    
    # Check if the slot is available
    available_slots = get_available_slots(dt.strftime("%Y-%m-%d"))
    return dt.strftime("%I:%M %p") in available_slots

def book_appointment_slot(phone_number: str, dt: datetime, service_type: str, recipient: str = "self") -> str:
    """Book a specific appointment slot."""
    # Get customer information if available
    customer_info = get_customer_info(phone_number)
    customer_name = customer_info.get('name', '')
    
    # Create a new appointment
    appointment_id = f"APPT-{int(get_current_datetime().timestamp())}"
    new_appointment = {
        'id': appointment_id,
        'phone': phone_number,
        'datetime': dt.strftime("%Y-%m-%d %H:%M:%S"),
        'service_type': service_type,
        'recipient': recipient,  # Add recipient field
        'customer_name': customer_name,  # Add customer name
        'created_at': get_current_datetime().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    logger.info(f"Attempting to book appointment: {new_appointment}")
    
    # Add to the sheet
    if add_appointment_to_sheet(new_appointment):
        logger.info(f"Successfully booked appointment {appointment_id} for {customer_name or phone_number} at {dt}")
        return appointment_id
    else:
        error_msg = "Error booking appointment - could not add to sheet"
        logger.error(error_msg)
        raise Exception(error_msg)

def schedule_reminder(phone_number: str, appointment_id: str, reminder_dt: datetime):
    """Schedule a reminder for the appointment."""
    # Implementation of scheduling a reminder
    pass

def cancel_appointment(phone: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel an existing appointment."""
    try:
        # Find the appointment
        appointment_id = entities.get('appointment_id')
        appointment = find_appointment(phone, appointment_id)
        
        if not appointment:
            return {
                'success': False,
                'message': "I couldn't find any upcoming appointments for you. If you need help, please provide more details."
            }
        
        # Cancel the appointment
        if remove_appointment_from_sheet(appointment['id']):
            appt_datetime = dateutil_parse(appointment['datetime'])
            
            # Notify the barber about the cancellation
            barber_phone = os.environ.get('BARBER_PHONE_NUMBER', '+12345678901')
            notify_barber_of_cancellation(barber_phone, phone, appt_datetime)
            
            return {
                'success': True,
                'message': f"Your appointment for {appt_datetime.strftime('%A, %B %d at %I:%M %p')} has been canceled."
            }
        else:
            return {
                'success': False,
                'message': "There was an error canceling your appointment. Please try again later."
            }
    
    except Exception as e:
        logger.error(f"Error canceling appointment: {e}")
        return {
            'success': False,
            'message': "There was an unexpected error canceling your appointment. Please try again."
        }

def reschedule_appointment(phone: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Reschedule an existing appointment."""
    try:
        # Extract entities
        date_str = entities.get('date')
        time_str = entities.get('time')
        appointment_id = entities.get('appointment_id')
        
        if not date_str or not time_str:
            return {
                'success': False,
                'message': "I need both a date and time to reschedule your appointment. For example: 'Reschedule to tomorrow at 3pm'"
            }
        
        # Find the appointment
        appointment = find_appointment(phone, appointment_id)
        
        if not appointment:
            return {
                'success': False,
                'message': "I couldn't find any upcoming appointments for you to reschedule. If you need help, please provide more details."
            }
        
        # Parse the new date and time
        new_datetime = parse_date_time(date_str, time_str)
        
        if not new_datetime:
            return {
                'success': False,
                'message': f"I couldn't understand the date and time you provided. Please try something like 'tomorrow at 3pm' or 'Friday at 10:30am'."
            }
        
        # Check if it's a valid appointment time
        if not is_valid_appointment_time(new_datetime):
            return {
                'success': False,
                'message': f"Sorry, we can't reschedule to that time. We're open Monday to Saturday from {OPENING_HOUR}am to {CLOSING_HOUR}pm."
            }
        
        # Check if the slot is available
        available_slots = get_available_slots(date_str)
        new_time_str = new_datetime.strftime("%I:%M %p")
        if new_time_str not in available_slots:
            return {
                'success': False,
                'message': f"Sorry, that time slot is not available. Here are the available times on {new_datetime.strftime('%A, %B %d')}: {', '.join(available_slots)}"
            }
        
        # Update the appointment
        old_datetime = dateutil_parse(appointment['datetime'])
        new_data = {
            'datetime': new_datetime.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if update_appointment_in_sheet(appointment['id'], new_data):
            # Schedule reminders for the new time
            schedule_reminders(phone, new_datetime)
            
            # Notify the barber about the reschedule
            barber_phone = os.environ.get('BARBER_PHONE_NUMBER', '+12345678901')
            notify_barber_of_reschedule(barber_phone, phone, old_datetime, new_datetime)
            
            return {
                'success': True,
                'message': f"Your appointment has been rescheduled from {old_datetime.strftime('%A, %B %d at %I:%M %p')} to {new_datetime.strftime('%A, %B %d at %I:%M %p')}. You'll receive a reminder 24 hours and 1 hour before your appointment.",
                'appointment_time': new_datetime
            }
        else:
            return {
                'success': False,
                'message': "There was an error rescheduling your appointment. Please try again later."
            }
    
    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}")
        return {
            'success': False,
            'message': "There was an unexpected error rescheduling your appointment. Please try again."
        }

def get_upcoming_appointments(phone: str) -> str:
    """Get a list of upcoming appointments for a customer."""
    try:
        appointments = get_appointments_for_phone(phone)
        
        if not appointments:
            return "You don't have any upcoming appointments."
        
        result = "Your upcoming appointments:\n"
        for idx, appt in enumerate(appointments[:5], 1):  # Show up to 5 upcoming appointments
            dt = dateutil_parse(appt['datetime'])
            recipient_info = ""
            if 'recipient' in appt and appt['recipient'] and appt['recipient'].lower() != 'self':
                recipient_info = f" for {appt['recipient']}"
            result += f"{idx}. {dt.strftime('%A, %B %d at %I:%M %p')}{recipient_info} - {appt['service_type']}\n"
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting upcoming appointments: {e}")
        return "There was an error retrieving your appointments. Please try again."

def get_upcoming_appointments_raw(phone: str) -> List[Dict[str, Any]]:
    """Get raw data for upcoming appointments for a customer.
    
    Used by agent to count and enforce appointment limits.
    
    Args:
        phone: The customer's phone number
        
    Returns:
        List of appointment dictionaries
    """
    try:
        appointments = get_appointments_for_phone(phone)
        if not appointments:
            return []
        
        # Return raw appointment data for processing
        return appointments
    
    except Exception as e:
        logger.error(f"Error getting raw upcoming appointments: {e}")
        return []

def check_availability(date_str: str = None) -> str:
    """Check availability for a given date and return available time slots."""
    try:
        now = get_current_datetime()
        
        # If no date specified, use tomorrow
        if not date_str:
            target_date = now.date() + timedelta(days=1)
            requested_date_str = target_date.strftime("%Y-%m-%d")
            logger.info(f"No date specified, defaulting to tomorrow: {requested_date_str}")
        else:
            # Try to parse the date
            logger.info(f"Checking availability for requested date: {date_str}")
            requested_date_str = date_str.strip()
            
            # If date is in ISO format (YYYY-MM-DD)
            if re.match(r'^\d{4}-\d{2}-\d{2}$', requested_date_str):
                target_date = datetime.strptime(requested_date_str, "%Y-%m-%d").date()
                logger.info(f"Parsed as ISO format date: {target_date}")
            else:
                # Try to interpret as a date string
                try:
                    parsed_date = dateutil_parse(requested_date_str, fuzzy=True)
                    target_date = parsed_date.date()
                    requested_date_str = target_date.strftime("%Y-%m-%d")
                    logger.info(f"Parsed date using dateutil: {target_date}")
                except:
                    # Default to tomorrow if parsing fails
                    target_date = now.date() + timedelta(days=1)
                    requested_date_str = target_date.strftime("%Y-%m-%d")
                    logger.warning(f"Could not parse date '{date_str}', using tomorrow: {requested_date_str}")
        
        # Ensure we're working with datetime objects for comparison
        current_date = now.date()
        logger.info(f"Current date: {current_date}")
        logger.info(f"Parsed requested date: {target_date}")
        
        # Check if the date is in the past
        if target_date < current_date:
            logger.warning(f"Requested date {target_date} is in the past")
            # Use tomorrow's date instead
            target_date = current_date + timedelta(days=1)
            requested_date_str = target_date.strftime("%Y-%m-%d")
            logger.info(f"Using tomorrow's date instead: {requested_date_str}")

        # Get available slots for the date
        target_date_full = datetime.combine(target_date, time(0, 0, 0))
        logger.info(f"Using target date: {target_date_full}")
        
        # Get available slots for the date
        available_slots = get_available_slots(requested_date_str)
        
        # Format the response
        formatted_date = format_date_for_display(requested_date_str)
        
        if not available_slots:
            nearby_dates = []
            # Check next 3 business days for availability
            for i in range(1, 4):
                check_date = target_date + timedelta(days=i)
                check_date_str = check_date.strftime("%Y-%m-%d")
                
                # Skip Sundays
                if check_date.weekday() == 6:  # Sunday
                    continue
                    
                nearby_slots = get_available_slots(check_date_str)
                if nearby_slots:
                    nearby_dates.append(check_date_str)
            
            if nearby_dates:
                alt_dates = ", ".join([format_date_for_display(d) for d in nearby_dates])
                return f"I'm sorry, but there are no available slots for {formatted_date}. However, I found availability on: {alt_dates}. Would you like to see the available times for any of these dates?"
            else:
                return f"I'm sorry, but there are no available slots for {formatted_date} or the next few business days. Would you like to check a different date?"
        
        # Format slots into morning, afternoon, evening categories
        morning_slots = []
        afternoon_slots = []
        evening_slots = []
        
        for slot in available_slots:
            slot_time = dateutil_parse(slot).time()
            formatted_time = datetime.strptime(f"{slot_time.hour}:{slot_time.minute}", "%H:%M").strftime("%I:%M %p")
            
            if slot_time.hour < 12:
                morning_slots.append(formatted_time)
            elif slot_time.hour < 17:
                afternoon_slots.append(formatted_time)
            else:
                evening_slots.append(formatted_time)
        
        response = f"Available slots for {formatted_date}:"
        
        if morning_slots:
            response += f"\nMorning: {', '.join(morning_slots)}"
        if afternoon_slots:
            response += f"\nAfternoon: {', '.join(afternoon_slots)}"
        if evening_slots:
            response += f"\nEvening: {', '.join(evening_slots)}"
        
        logger.info(f"Returning availability for {requested_date_str} with {len(available_slots)} slots")
        return response
        
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return "I'm having trouble checking appointment availability right now. Please try again later or contact us directly."

def is_working_day(date_str: str) -> bool:
    """Check if a date is a working day."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        return date_obj.weekday() < 6  # Monday-Saturday are working days (0-5)
    except Exception as e:
        logger.error(f"Error checking if date is a working day: {e}")
        return False

def format_date_for_display(date_str: str) -> str:
    """Format a date string (YYYY-MM-DD) for user-friendly display."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        return date_obj.strftime("%A, %B %d")  # e.g., "Monday, October 7"
    except Exception as e:
        logger.error(f"Error formatting date for display: {e}")
        return date_str

# Add functions to save and retrieve customer data
@rate_limited
def save_customer_info(phone_number: str, customer_info: Dict[str, Any]) -> bool:
    """Save or update customer information in the database."""
    client = get_sheet_client()
    
    if client:
        try:
            # Check if we have a Customer Info sheet
            sheet = client.open_by_key(SHEET_ID)
            customer_sheet = None
            
            try:
                customer_sheet = sheet.worksheet("Customers")
                logger.info("Found existing Customers worksheet")
            except:
                # Create the worksheet
                logger.info("Creating new Customers worksheet")
                customer_sheet = sheet.add_worksheet(title="Customers", rows=100, cols=10)
                # Add headers
                customer_sheet.append_row(["phone", "name", "email", "preferences", "last_updated"])
            
            # Check if customer already exists
            try:
                cell = customer_sheet.find(phone_number)
                if cell:
                    # Update existing customer
                    row = cell.row
                    logger.info(f"Updating existing customer at row {row}")
                    
                    # Get existing data
                    existing_data = customer_sheet.row_values(row)
                    logger.info(f"Existing data: {existing_data}")
                    
                    # Update cells
                    if 'name' in customer_info:
                        customer_sheet.update_cell(row, 2, customer_info['name'])
                    if 'email' in customer_info:
                        customer_sheet.update_cell(row, 3, customer_info['email'])
                    if 'preferences' in customer_info:
                        customer_sheet.update_cell(row, 4, json.dumps(customer_info['preferences']))
                    
                    # Update last_updated timestamp
                    customer_sheet.update_cell(row, 5, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    return True
                else:
                    # Add new customer
                    logger.info(f"Adding new customer: {phone_number}")
                    row_data = [
                        phone_number,
                        customer_info.get('name', ''),
                        customer_info.get('email', ''),
                        json.dumps(customer_info.get('preferences', {})),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ]
                    customer_sheet.append_row(row_data)
                    return True
            except Exception as e:
                logger.error(f"Error updating customer data: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving customer info: {e}")
            return False
    else:
        # Use the mock database
        logger.info(f"Using mock database to store customer info for {phone_number}")
        MOCK_DB["customers"][phone_number] = {
            **customer_info,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return True

@rate_limited
def get_customer_info(phone_number: str) -> Dict[str, Any]:
    """Retrieve customer information from the database."""
    client = get_sheet_client()
    
    if client:
        try:
            customer_sheet = client.open_by_key(SHEET_ID).worksheet("Customers")
            try:
                cell = customer_sheet.find(phone_number)
                if cell:
                    # Get data for this customer
                    row_data = customer_sheet.row_values(cell.row)
                    if len(row_data) >= 5:
                        return {
                            "phone": row_data[0],
                            "name": row_data[1],
                            "email": row_data[2],
                            "preferences": json.loads(row_data[3]) if row_data[3] else {},
                            "last_updated": row_data[4]
                        }
                # Customer not found
                return {}
            except Exception as e:
                logger.error(f"Error finding customer: {e}")
                return {}
        except Exception as e:
            logger.error(f"Error getting customer info: {e}")
            return {}
    else:
        # Use the mock database
        logger.info(f"Using mock database to retrieve customer info for {phone_number}")
        return MOCK_DB["customers"].get(phone_number, {}) 