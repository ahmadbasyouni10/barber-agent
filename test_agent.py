#!/usr/bin/env python3
"""
Test script for the barber appointment agent.
This allows you to interact with the agent via command line,
without requiring Twilio setup.
"""

import os
from dotenv import load_dotenv
from chains.agent import process_incoming_message
import sys

# Load environment variables
load_dotenv()

def main():
    """Run an interactive test session with the agent."""
    print("Barber Agent Test Interface")
    print("==========================")
    print("Type messages as if you were texting the barber agent.")
    print("The agent will respond just like it would via SMS.")
    print("Type 'exit' or 'quit' to end the session.\n")
    
    # Get a test phone number
    phone_number = input("Enter a test phone number (e.g. +1234567890): ") or "+1234567890"
    
    while True:
        # Get user input
        message = input("\n> ")
        
        # Check if the user wants to exit
        if message.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
        
        # Process the message
        try:
            print("\nProcessing...")
            response = process_incoming_message(phone_number, message)
            print(f"\nAgent: {response}")
        except Exception as e:
            print(f"\nError: {e}")
            print("There was an error processing your message. Please try again.")

if __name__ == "__main__":
    # Make sure the LANGSMITH_TRACING environment variable is set
    if not os.environ.get('LANGSMITH_TRACING'):
        print("Warning: LANGSMITH_TRACING is not set. Setting to 'true' for testing.")
        os.environ['LANGSMITH_TRACING'] = "true"
    
    # Run the test interface
    main() 