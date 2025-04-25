#!/usr/bin/env python3
"""
Helper script for setting up Twilio integration.
This script guides you through the process and checks your setup.
"""

import os
import sys
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException, TwilioException

# Load environment variables
load_dotenv()

def print_step(step_num, step_text):
    """Print a step in the setup process."""
    print(f"\n--- Step {step_num}: {step_text} ---")

def check_twilio_credentials():
    """Check if Twilio credentials are set in environment variables."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or account_sid == 'your_twilio_account_sid_here':
        print("❌ Twilio Account SID not set in .env file!")
        print("   Find your Account SID at: https://console.twilio.com/")
        return False
    
    if not auth_token or auth_token == 'your_twilio_auth_token_here':
        print("❌ Twilio Auth Token not set in .env file!")
        print("   Find your Auth Token at: https://console.twilio.com/")
        return False
    
    print("✅ Twilio credentials found in .env file!")
    return True

def check_twilio_phone_number():
    """Check if Twilio phone number is set in environment variables."""
    phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if not phone_number or phone_number == 'your_twilio_phone_number_here':
        print("❌ Twilio Phone Number not set in .env file!")
        print("   You can find or buy a phone number at: https://console.twilio.com/")
        return False
    
    # Check if the number includes a plus sign
    if not phone_number.startswith('+'):
        print("⚠️ Twilio Phone Number should include the country code with a plus sign (e.g., +12345678901)")
    
    print(f"✅ Twilio Phone Number found: {phone_number}")
    return True

def check_barber_phone_number():
    """Check if barber phone number is set in environment variables."""
    phone_number = os.environ.get('BARBER_PHONE_NUMBER')
    
    if not phone_number or phone_number == 'your_phone_number_here':
        print("❌ Barber Phone Number not set in .env file!")
        print("   This is the number that will receive notifications about bookings.")
        return False
    
    # Check if the number includes a plus sign
    if not phone_number.startswith('+'):
        print("⚠️ Barber Phone Number should include the country code with a plus sign (e.g., +12345678901)")
    
    print(f"✅ Barber Phone Number found: {phone_number}")
    return True

def test_twilio_connection():
    """Test if we can connect to Twilio API."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token or account_sid == 'your_twilio_account_sid_here' or auth_token == 'your_twilio_auth_token_here':
        print("❌ Cannot test Twilio connection - missing credentials.")
        return False
    
    try:
        client = Client(account_sid, auth_token)
        
        # Just try to get account info to test the connection
        account = client.api.accounts(account_sid).fetch()
        
        print("✅ Successfully connected to Twilio API!")
        print(f"   Account Status: {account.status}")
        return True
    except TwilioRestException as e:
        print(f"❌ Error connecting to Twilio API: {e}")
        if e.status == 401:
            print("   Your Account SID or Auth Token may be incorrect.")
        return False
    except Exception as e:
        print(f"❌ Error connecting to Twilio API: {e}")
        return False

def verify_phone_number():
    """Verify that the Twilio phone number exists in your account."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if not account_sid or not auth_token or not phone_number:
        print("❌ Cannot verify phone number - missing credentials or phone number.")
        return False
    
    try:
        client = Client(account_sid, auth_token)
        
        # Get list of phone numbers in the account
        incoming_phone_numbers = client.incoming_phone_numbers.list()
        phone_numbers = [number.phone_number for number in incoming_phone_numbers]
        
        # Check if our phone number is in the list
        if phone_number in phone_numbers:
            print(f"✅ Verified: Phone number {phone_number} exists in your Twilio account!")
            return True
        else:
            # Try normalizing the phone number format
            normalized_phone = phone_number
            if not normalized_phone.startswith('+'):
                normalized_phone = '+' + normalized_phone
            
            if normalized_phone in phone_numbers:
                print(f"✅ Verified: Phone number {normalized_phone} exists in your Twilio account!")
                print(f"   (Note: You should use this exact format in your .env file)")
                return True
            
            print(f"❌ Phone number {phone_number} not found in your Twilio account!")
            print(f"   Your account has these phone numbers:")
            for number in phone_numbers:
                print(f"   - {number}")
            return False
    except Exception as e:
        print(f"❌ Error verifying phone number: {e}")
        return False

def send_test_message():
    """Send a test SMS message using Twilio."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_number = os.environ.get('TWILIO_PHONE_NUMBER')
    barber_number = os.environ.get('BARBER_PHONE_NUMBER')
    
    if not account_sid or not auth_token or not twilio_number or not barber_number:
        print("❌ Cannot send test message - missing credentials or phone numbers.")
        return False
    
    # Ask for confirmation before sending
    confirm = input("Would you like to send a test SMS to the barber's phone number? (y/n): ").lower()
    if confirm != 'y':
        print("Skipping test message.")
        return None
    
    try:
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body="This is a test message from your Barber Appointment System. If you're receiving this, your Twilio setup is working!",
            from_=twilio_number,
            to=barber_number
        )
        
        print(f"✅ Test message sent! Message SID: {message.sid}")
        print(f"   Status: {message.status}")
        return True
    except TwilioRestException as e:
        print(f"❌ Error sending test message: {e}")
        if e.code == 21608:
            print("   Your Twilio account may not be verified yet or doesn't have sufficient funds.")
        elif e.code == 21211:
            print("   The 'to' phone number is invalid. Make sure it includes the country code.")
        return False
    except Exception as e:
        print(f"❌ Error sending test message: {e}")
        return False

def main():
    """Run the Twilio setup assistant."""
    print("\n=== Twilio Setup Assistant ===\n")
    print("This script will help you set up and test your Twilio integration.")
    print("Make sure you have already:")
    print("1. Created a Twilio account at https://www.twilio.com/")
    print("2. Purchased a phone number with SMS capabilities")
    print("3. Found your Account SID and Auth Token")
    
    # Step 1: Check if Twilio credentials are set
    print_step(1, "Checking Twilio Credentials")
    creds_ok = check_twilio_credentials()
    
    # Step 2: Check if Twilio phone number is set
    print_step(2, "Checking Twilio Phone Number")
    twilio_number_ok = check_twilio_phone_number()
    
    # Step 3: Check if barber phone number is set
    print_step(3, "Checking Barber Phone Number")
    barber_number_ok = check_barber_phone_number()
    
    # Step 4: Test Twilio API connection
    print_step(4, "Testing Twilio API Connection")
    if creds_ok:
        connection_ok = test_twilio_connection()
    else:
        print("⚠️ Skipping API connection test - fix the credential issues first.")
        connection_ok = False
    
    # Step 5: Verify phone number
    print_step(5, "Verifying Twilio Phone Number")
    if creds_ok and twilio_number_ok and connection_ok:
        phone_verified = verify_phone_number()
    else:
        print("⚠️ Skipping phone number verification - fix the issues above first.")
        phone_verified = False
    
    # Step 6: Send test message
    print_step(6, "Sending Test SMS")
    if creds_ok and twilio_number_ok and barber_number_ok and connection_ok and phone_verified:
        message_sent = send_test_message()
    else:
        print("⚠️ Skipping test message - fix the issues above first.")
        message_sent = None
    
    # Print summary
    print("\n=== Setup Summary ===")
    print(f"Twilio Credentials: {'✅ OK' if creds_ok else '❌ Missing/Invalid'}")
    print(f"Twilio Phone Number: {'✅ OK' if twilio_number_ok else '❌ Missing/Invalid'}")
    print(f"Barber Phone Number: {'✅ OK' if barber_number_ok else '❌ Missing/Invalid'}")
    print(f"Twilio API Connection: {'✅ OK' if connection_ok else '❌ Failed'}")
    print(f"Phone Number Verification: {'✅ OK' if phone_verified else '❌ Failed'}")
    if message_sent is not None:
        print(f"Test Message: {'✅ Sent' if message_sent else '❌ Failed'}")
    else:
        print("Test Message: ⚠️ Skipped")
    
    if creds_ok and twilio_number_ok and barber_number_ok and connection_ok and phone_verified:
        print("\n🎉 Twilio integration is ready to use!")
        print("You can now run the barber appointment system.")
    else:
        print("\n⚠️ Please fix the issues above before continuing.")

if __name__ == "__main__":
    main() 