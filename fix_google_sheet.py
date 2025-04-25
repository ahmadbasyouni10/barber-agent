#!/usr/bin/env python3
"""
Google Sheet Repair Tool for Barber Agent.

This script checks your Google Sheets integration, diagnoses common issues,
and attempts to fix them automatically. It's useful when appointments aren't 
being saved correctly to the sheet.
"""

import os
import sys
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("google_sheet_repair")

# Load environment variables
load_dotenv()

# Constants for Google Sheets setup
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
CREDS_FILE = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID')

def check_environment_variables():
    """Check if required environment variables are set"""
    print("📋 Checking environment variables...")
    missing_vars = []
    
    if not SHEET_ID:
        missing_vars.append("GOOGLE_SHEET_ID")
    
    if not CREDS_FILE:
        missing_vars.append("GOOGLE_SHEETS_CREDENTIALS_FILE")
    
    if missing_vars:
        print("❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    
    print("✅ Environment variables are correctly set")
    print(f"   - GOOGLE_SHEET_ID = {SHEET_ID}")
    print(f"   - GOOGLE_SHEETS_CREDENTIALS_FILE = {CREDS_FILE}")
    return True

def check_credentials_file():
    """Check if credentials file exists and is valid"""
    print("\n📝 Checking credentials file...")
    if not os.path.exists(CREDS_FILE):
        print(f"❌ Credentials file not found at {os.path.abspath(CREDS_FILE)}")
        return False
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPES)
        print("✅ Credentials file is valid")
        return True
    except Exception as e:
        print(f"❌ Error reading credentials file: {e}")
        return False

def check_sheet_access():
    """Check if we can access the Google Sheet"""
    print("\n🔑 Checking Google Sheet access...")
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID)
        
        # Check if sheets exists
        worksheets = sheet.worksheets()
        print(f"✅ Successfully accessed Google Sheet '{sheet.title}'")
        print(f"   - Found {len(worksheets)} worksheets: {[ws.title for ws in worksheets]}")
        return client, sheet, worksheets
    except gspread.exceptions.APIError as e:
        print(f"❌ API Error: {e}")
        return None, None, None
    except Exception as e:
        print(f"❌ Error accessing sheet: {e}")
        return None, None, None

def check_appointments_worksheet(sheet, worksheets):
    """Check if Appointments worksheet exists and has correct headers"""
    print("\n📊 Checking Appointments worksheet...")
    appointments_ws = None
    
    for ws in worksheets:
        if ws.title == "Appointments":
            appointments_ws = ws
            break
    
    if not appointments_ws:
        print("❌ No 'Appointments' worksheet found")
        return None
    
    # Check headers
    expected_headers = ['id', 'phone', 'datetime', 'service_type', 'created_at']
    try:
        actual_headers = appointments_ws.row_values(1)
        print(f"   - Headers: {actual_headers}")
        
        missing_headers = [h for h in expected_headers if h not in actual_headers]
        if missing_headers:
            print(f"❌ Missing headers: {missing_headers}")
            return appointments_ws
        
        print("✅ Appointments worksheet has correct headers")
        return appointments_ws
    except Exception as e:
        print(f"❌ Error checking headers: {e}")
        return appointments_ws

def fix_worksheet(sheet, appointments_ws):
    """Fix the Appointments worksheet if needed"""
    print("\n🔧 Fixing Appointments worksheet...")
    if appointments_ws:
        # Worksheet exists but might have wrong headers
        try:
            appointments_ws.clear()
            appointments_ws.append_row(['id', 'phone', 'datetime', 'service_type', 'created_at'])
            print("✅ Reset 'Appointments' worksheet with correct headers")
        except Exception as e:
            print(f"❌ Error resetting worksheet: {e}")
    else:
        # Need to create the worksheet
        try:
            appointments_ws = sheet.add_worksheet(title="Appointments", rows=1000, cols=20)
            appointments_ws.append_row(['id', 'phone', 'datetime', 'service_type', 'created_at'])
            print("✅ Created new 'Appointments' worksheet with correct headers")
        except Exception as e:
            print(f"❌ Error creating worksheet: {e}")

def test_write_appointment(appointments_ws):
    """Test writing a sample appointment to the sheet"""
    print("\n📝 Testing appointment write...")
    import datetime
    import uuid
    
    try:
        test_id = f"TEST-{uuid.uuid4().hex[:8]}"
        test_phone = "+15551234567"
        test_datetime = datetime.datetime.now() + datetime.timedelta(days=1)
        test_datetime_str = test_datetime.strftime("%Y-%m-%d %H:%M:%S")
        test_service = "haircut-test"
        test_created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        appointments_ws.append_row([test_id, test_phone, test_datetime_str, test_service, test_created])
        print("✅ Successfully wrote test appointment to sheet")
        
        # Try to read it back
        rows = appointments_ws.get_all_records()
        test_found = False
        for row in rows:
            if row.get('id') == test_id:
                test_found = True
                break
        
        if test_found:
            print("✅ Successfully read test appointment from sheet")
        else:
            print("❌ Could not read back test appointment")
        
        # Clean up by removing the test row
        try:
            cell = appointments_ws.find(test_id)
            if cell:
                appointments_ws.delete_row(cell.row)
                print("✅ Successfully removed test appointment")
        except:
            print("⚠️ Could not clean up test appointment, but this is not critical")
        
        return test_found
    except Exception as e:
        print(f"❌ Error testing appointment write: {e}")
        return False

def main():
    """Main function to check and fix Google Sheets integration"""
    print("\n" + "="*60)
    print("  Google Sheet Repair Tool for Barber Agent".center(60))
    print("="*60)
    
    # Step 1: Check environment variables
    if not check_environment_variables():
        print("\n❌ Please set the required environment variables in your .env file and try again.")
        sys.exit(1)
    
    # Step 2: Check credentials file
    if not check_credentials_file():
        print("\n❌ Please fix your credentials file and try again.")
        sys.exit(1)
    
    # Step 3: Check Google Sheet access
    client, sheet, worksheets = check_sheet_access()
    if not sheet:
        print("\n❌ Could not access Google Sheet. Please check your Sheet ID and permissions.")
        sys.exit(1)
    
    # Step 4: Check Appointments worksheet
    appointments_ws = check_appointments_worksheet(sheet, worksheets)
    
    # Step 5: Fix worksheet if needed
    if not appointments_ws or input("\nWould you like to reset the Appointments worksheet? (y/n): ").lower() == 'y':
        fix_worksheet(sheet, appointments_ws)
        # Get the worksheet again if it was just created
        if not appointments_ws:
            for ws in sheet.worksheets():
                if ws.title == "Appointments":
                    appointments_ws = ws
                    break
    
    # Step 6: Test writing an appointment
    if appointments_ws:
        success = test_write_appointment(appointments_ws)
        if success:
            print("\n✅ Google Sheets integration is working correctly!")
        else:
            print("\n❌ There are still issues with writing to the Google Sheet.")
            print("   Please check your permissions and service account settings.")
    else:
        print("\n❌ Could not find or create Appointments worksheet.")
    
    print("\nDiagnostic complete.")

if __name__ == "__main__":
    main() 