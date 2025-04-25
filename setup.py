#!/usr/bin/env python3
"""
Main setup script for the Barber Appointment System.
This script guides you through all the necessary setup steps.
"""

import os
import subprocess
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_header(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60 + "\n")

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import flask
        import twilio
        import gspread
        import oauth2client
        import dotenv
        import apscheduler
        import langchain
        
        print("✅ All required Python packages are installed.")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_env_file():
    """Check if .env file exists and has basic structure."""
    if not os.path.exists(".env"):
        print("❌ .env file not found!")
        print("Creating a new .env file from .env.example...")
        
        if os.path.exists(".env.example"):
            # Copy .env.example to .env
            with open(".env.example", "r") as example:
                with open(".env", "w") as env:
                    env.write(example.read())
            print("✅ Created .env file. You'll need to update it with your credentials.")
        else:
            print("❌ .env.example file not found! Please create a .env file manually.")
        
        return False
    else:
        print("✅ .env file found.")
        return True

def run_setup_script(script_name, step_name):
    """Run a setup script and wait for it to complete."""
    print(f"\nRunning {step_name}...")
    try:
        subprocess.run(["python", script_name], check=True)
        print(f"\n✅ {step_name} completed.")
        return True
    except subprocess.CalledProcessError:
        print(f"\n❌ {step_name} failed. Please check the errors above.")
        return False
    except FileNotFoundError:
        print(f"\n❌ {script_name} not found!")
        return False

def setup_webhooks():
    """Provide guidance on setting up webhooks."""
    print("\n--- Setting Up Webhooks ---")
    print("To receive SMS messages from Twilio, you need to expose your Flask app publicly.")
    print("\nOptions:")
    print("1. Deploy to a cloud service (Heroku, Render, etc.)")
    print("2. Use ngrok for local development")
    
    print("\nFor local development with ngrok:")
    print("1. Install ngrok from https://ngrok.com/")
    print("2. Run: ngrok http 5000")
    print("3. Copy the https URL (e.g., https://abc123.ngrok.io)")
    
    print("\nIn your Twilio account:")
    print("1. Go to Phone Numbers > Manage > Active Numbers")
    print("2. Click on your number")
    print("3. Scroll to 'Messaging' section")
    print("4. Set the webhook URL for incoming messages to:")
    print("   YOUR_NGROK_URL/sms (e.g., https://abc123.ngrok.io/sms)")
    print("5. Make sure HTTP POST is selected")
    print("6. Save your changes")
    
    input("\nPress Enter when you have set up your webhook or to continue...")
    return True

def main():
    """Run the main setup process."""
    print_header("Barber Appointment System Setup")
    print("This script will guide you through setting up all components.")
    print("Follow the instructions for each step.")
    
    # Step 1: Check dependencies
    print_header("Step 1: Checking Dependencies")
    deps_ok = check_dependencies()
    
    # Step 2: Check .env file
    print_header("Step 2: Checking Environment File")
    env_ok = check_env_file()
    
    # Step 3: Set up Twilio
    print_header("Step 3: Setting Up Twilio")
    print("You'll need a Twilio account with:")
    print("- Account SID and Auth Token")
    print("- A phone number with SMS capabilities")
    input("Press Enter when you're ready to continue...")
    twilio_ok = run_setup_script("setup_twilio.py", "Twilio setup")
    
    # Step 4: Set up Google Sheets
    print_header("Step 4: Setting Up Google Sheets")
    print("You'll need:")
    print("- A Google Cloud project with Sheets API enabled")
    print("- A service account with a JSON key file")
    print("- A Google Sheet shared with the service account")
    input("Press Enter when you're ready to continue...")
    sheets_ok = run_setup_script("setup_google.py", "Google Sheets setup")
    
    # Step 5: Set up webhooks
    print_header("Step 5: Setting Up Webhooks")
    webhooks_ok = setup_webhooks()
    
    # Step 6: Test the application
    print_header("Step 6: Testing the Application")
    print("You can test the application in two ways:")
    print("1. Run the command-line test interface:")
    print("   python test_agent.py")
    print("\n2. Run the full Flask application:")
    print("   python app.py")
    print("   (Then send an SMS to your Twilio number)")
    
    # Print overall status
    print_header("Setup Summary")
    print(f"Dependencies: {'✅ OK' if deps_ok else '❌ Issue'}")
    print(f"Environment File: {'✅ OK' if env_ok else '❌ Issue'}")
    print(f"Twilio Integration: {'✅ OK' if twilio_ok else '❌ Issue'}")
    print(f"Google Sheets Integration: {'✅ OK' if sheets_ok else '❌ Issue'}")
    print(f"Webhook Configuration: {'✅ OK' if webhooks_ok else '❌ Issue'}")
    
    all_ok = deps_ok and env_ok and twilio_ok and sheets_ok and webhooks_ok
    
    if all_ok:
        print("\n🎉 Congratulations! Your Barber Appointment System is ready to use!")
        print("Run 'python app.py' to start the server.")
    else:
        print("\n⚠️ There are some issues that need to be resolved.")
        print("Please fix the issues marked with ❌ before using the system.")

if __name__ == "__main__":
    main() 