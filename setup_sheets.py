#!/usr/bin/env python3
"""
Script to set up Google Sheets for the barber appointment system.
Run this script once to create the required worksheet and headers.
"""

import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Get Google Sheets credentials
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
CREDS_FILE = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_FILE')
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID')

def setup_sheets():
    """Set up the Google Sheets structure for the appointment system."""
    if not CREDS_FILE or not SHEET_ID:
        print("Error: Missing environment variables.")
        print("Make sure GOOGLE_SHEETS_CREDENTIALS_FILE and GOOGLE_SHEET_ID are set in .env")
        sys.exit(1)
        
    try:
        # Authenticate with Google Sheets API
        print(f"Authenticating with Google using credentials file: {CREDS_FILE}")
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPES)
        client = gspread.authorize(creds)
        
        # Open the spreadsheet
        print(f"Opening spreadsheet with ID: {SHEET_ID}")
        spreadsheet = client.open_by_key(SHEET_ID)
        
        # Check if Appointments worksheet already exists
        worksheet_list = spreadsheet.worksheets()
        worksheet_titles = [ws.title for ws in worksheet_list]
        
        if "Appointments" in worksheet_titles:
            print("Appointments worksheet already exists.")
            appointments_sheet = spreadsheet.worksheet("Appointments")
            
            # Check if headers are already set
            headers = appointments_sheet.row_values(1)
            if headers and len(headers) >= 5:
                print("Headers are already set.")
            else:
                # Set headers
                appointments_sheet.update('A1:E1', [['id', 'phone', 'datetime', 'service_type', 'created_at']])
                print("Headers have been set.")
        else:
            # Create Appointments worksheet
            print("Creating Appointments worksheet...")
            appointments_sheet = spreadsheet.add_worksheet(title="Appointments", rows=100, cols=5)
            
            # Set headers
            appointments_sheet.update('A1:E1', [['id', 'phone', 'datetime', 'service_type', 'created_at']])
            print("Appointments worksheet created with headers.")
        
        print("\nSetup complete! Your Google Sheet is ready to use with the barber appointment system.")
        
    except Exception as e:
        print(f"Error setting up Google Sheets: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_sheets() 