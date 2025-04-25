#!/usr/bin/env python3
"""
Helper script for setting up Google Sheets integration.
This script guides you through the process and checks your setup.
"""

import os
import json
import sys
from dotenv import load_dotenv, set_key
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load environment variables
load_dotenv()

def print_step(step_num, step_text):
    """Print a step in the setup process."""
    print(f"\n--- Step {step_num}: {step_text} ---")

def check_credentials_file():
    """Check if the credentials.json file exists."""
    creds_file = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
    if not os.path.exists(creds_file):
        print(f"❌ Credentials file '{creds_file}' not found!")
        print("   Please download your service account JSON key and save it as 'credentials.json'")
        print("   in the project directory.")
        return False
    
    # Validate the file
    try:
        with open(creds_file, 'r') as f:
            creds_data = json.load(f)
        
        required_fields = ['client_email', 'private_key', 'project_id']
        for field in required_fields:
            if field not in creds_data:
                print(f"❌ Credentials file is missing '{field}' field.")
                return False
        
        print(f"✅ Found valid credentials file!")
        print(f"   Service account email: {creds_data['client_email']}")
        print(f"   Project ID: {creds_data['project_id']}")
        return True
    except json.JSONDecodeError:
        print(f"❌ Credentials file is not valid JSON.")
        return False
    except Exception as e:
        print(f"❌ Error checking credentials file: {e}")
        return False

def check_sheet_id():
    """Check if the sheet ID is set in the environment variables."""
    sheet_id = os.environ.get('GOOGLE_SHEET_ID')
    if not sheet_id or sheet_id == 'your_google_sheet_id_here':
        print("❌ Google Sheet ID not set in .env file!")
        
        # Ask for the Sheet ID
        new_id = input("Enter your Google Sheet ID: ").strip()
        if new_id:
            # Update the .env file
            with open('.env', 'r') as f:
                env_lines = f.readlines()
            
            with open('.env', 'w') as f:
                for line in env_lines:
                    if line.startswith('GOOGLE_SHEET_ID='):
                        f.write(f'GOOGLE_SHEET_ID={new_id}\n')
                    else:
                        f.write(line)
            
            print("✅ Updated .env file with new Google Sheet ID!")
            os.environ['GOOGLE_SHEET_ID'] = new_id
            return True
        return False
    else:
        print(f"✅ Google Sheet ID found in .env file!")
        return True

def test_sheet_access():
    """Test if we can access the Google Sheet."""
    creds_file = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
    sheet_id = os.environ.get('GOOGLE_SHEET_ID')
    
    if not os.path.exists(creds_file) or not sheet_id:
        print("❌ Cannot test sheet access - missing credentials or sheet ID.")
        return False
    
    try:
        # Setup the credentials
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scopes)
        client = gspread.authorize(creds)
        
        # Try to open the sheet
        sheet = client.open_by_key(sheet_id)
        worksheets = sheet.worksheets()
        
        print(f"✅ Successfully connected to Google Sheet!")
        print(f"   Sheet title: {sheet.title}")
        print(f"   Worksheets: {', '.join([ws.title for ws in worksheets])}")
        
        # Check if we already have the Appointments worksheet
        if 'Appointments' in [ws.title for ws in worksheets]:
            print("✅ 'Appointments' worksheet already exists!")
        else:
            # Ask if we should create it
            create = input("   'Appointments' worksheet doesn't exist. Create it? (y/n): ").lower()
            if create == 'y':
                # Create the worksheet
                worksheet = sheet.add_worksheet(title='Appointments', rows=100, cols=5)
                # Add headers
                worksheet.update('A1:E1', [['id', 'phone', 'datetime', 'service_type', 'created_at']])
                print("✅ Created 'Appointments' worksheet with headers!")
        
        return True
    except Exception as e:
        print(f"❌ Error accessing Google Sheet: {e}")
        print("   Common issues:")
        print("   - Did you share the sheet with the service account email?")
        print("   - Is the Sheet ID correct?")
        print("   - Are the APIs enabled in Google Cloud Console?")
        return False

def main():
    """Run the Google Sheets setup assistant."""
    print("\n=== Google Sheets Setup Assistant ===\n")
    print("This script will help you set up and test your Google Sheets integration.")
    
    # Step 1: Check if credentials file exists
    print_step(1, "Checking Service Account Credentials")
    creds_ok = check_credentials_file()
    
    # Step 2: Check if Sheet ID is configured
    print_step(2, "Checking Google Sheet ID")
    sheet_id_ok = check_sheet_id()
    
    # Step 3: Test sheet access
    print_step(3, "Testing Google Sheet Access")
    if creds_ok and sheet_id_ok:
        access_ok = test_sheet_access()
    else:
        print("⚠️ Skipping sheet access test - fix the issues above first.")
        access_ok = False
    
    # Print summary
    print("\n=== Setup Summary ===")
    print(f"Service Account Credentials: {'✅ OK' if creds_ok else '❌ Missing/Invalid'}")
    print(f"Google Sheet ID: {'✅ OK' if sheet_id_ok else '❌ Missing/Invalid'}")
    print(f"Sheet Access: {'✅ OK' if access_ok else '❌ Failed'}")
    
    if creds_ok and sheet_id_ok and access_ok:
        print("\n🎉 Google Sheets integration is ready to use!")
        print("You can now run the barber appointment system.")
    else:
        print("\n⚠️ Please fix the issues above before continuing.")

if __name__ == "__main__":
    main() 