#!/usr/bin/env python
import logging
import sys
import traceback
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test direct datetime parsing
try:
    print("Testing direct datetime parsing...")
    tomorrow = datetime.now() + timedelta(days=1)
    print(f"Tomorrow calculated directly: {tomorrow}")
    
    # Test dateutil
    print("\nTesting dateutil.parser import...")
    try:
        from dateutil.parser import parse as dateutil_parse
        print("dateutil_parse imported successfully")
        
        test_parse = dateutil_parse("2023-01-01", fuzzy=True)
        print(f"Test parse result: {test_parse}")
    except ImportError as ie:
        print(f"ImportError: {ie}")
    except Exception as e:
        print(f"Error using dateutil.parser: {e}")
        traceback.print_exc()
    
    # Manual parsing attempt
    print("\nTesting manual parsing:")
    time_str = "4pm" 
    time_match = None
    
    # Try to extract hours/minutes from the time string
    if ":" in time_str:
        parts = time_str.split(":")
        hour = int(parts[0])
        # Handle minutes and AM/PM
        if "pm" in parts[1].lower() and hour < 12:
            hour += 12
        minute = int(parts[1].replace("am", "").replace("pm", "").strip())
    else:
        time_match = None
        try:
            import re
            # Look for patterns like "4pm", "10am", etc.
            time_match = re.search(r"(\d+)\s*(am|pm)?", time_str, re.IGNORECASE)
        except Exception as re_error:
            print(f"Regex error: {re_error}")
            
    if time_match:
        print(f"Regex matched: {time_match.groups()}")
        hour = int(time_match.group(1))
        am_pm = time_match.group(2)
        
        if am_pm and am_pm.lower() == "pm" and hour < 12:
            hour += 12
        print(f"Parsed time: {hour}:00")
        
        # Calculate final result
        base_date = tomorrow.date()
        result = datetime.combine(base_date, datetime.min.time().replace(hour=hour))
        print(f"Final parsed result: {result}")
    else:
        print("Time regex did not match")

    # Test the actual function
    print("\nTesting parse_datetime function...")
    try:
        from services.appointment_service import parse_datetime
        result = parse_datetime("tomorrow at 4pm")
        print(f"parse_datetime result: {result}")
    except Exception as e:
        print(f"Error in parse_datetime: {e}")
        traceback.print_exc()
        
except Exception as e:
    print(f"Unexpected error: {e}")
    traceback.print_exc()
