#!/usr/bin/env python3
"""
This script creates an ngrok tunnel for both the Flask app and Telegram webhook.
It allows your local development server to receive messages from Telegram and Twilio.
"""

import os
import sys
import time
import logging
import requests
import subprocess
from pyngrok import ngrok
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get Telegram bot token
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

def set_telegram_webhook(url):
    """Set the Telegram webhook to the ngrok URL"""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("No Telegram bot token found, skipping webhook setup")
        return False
    
    try:
        # Set the webhook
        webhook_url = f"{url}/telegram_webhook"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        response = requests.post(api_url, data={"url": webhook_url})
        
        if response.status_code == 200 and response.json().get("ok"):
            logger.info(f"Telegram webhook set to {webhook_url}")
            # Get webhook info to confirm
            info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
            info_response = requests.get(info_url)
            if info_response.status_code == 200:
                logger.info(f"Webhook info: {info_response.json()}")
            return True
        else:
            logger.error(f"Failed to set Telegram webhook: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error setting Telegram webhook: {e}")
        return False

def main():
    """Create ngrok tunnel and set Telegram webhook"""
    try:
        # Check if ngrok is already running
        tunnels = ngrok.get_tunnels()
        if tunnels:
            logger.info(f"Existing ngrok tunnels found: {tunnels}")
            
            # Kill existing tunnels
            logger.info("Killing existing tunnels...")
            for tunnel in tunnels:
                ngrok.disconnect(tunnel.public_url)
            
        # Start a new tunnel on port 5000 (Flask default)
        logger.info("Starting new ngrok tunnel on port 5000...")
        http_tunnel = ngrok.connect(5000, "http")
        
        # Get the public URL
        public_url = http_tunnel.public_url
        logger.info(f"Public URL: {public_url}")
        
        # Set environment variable for the Flask app to use
        os.environ["PUBLIC_URL"] = public_url
        
        # Set the Telegram webhook
        if TELEGRAM_BOT_TOKEN:
            set_telegram_webhook(public_url)
            logger.info(f"Telegram webhook set to: {public_url}/telegram_webhook")
            logger.info(f"Test your bot by sending a message to it on Telegram")
        
        # Display Twilio webhook URL
        logger.info(f"Twilio SMS webhook URL: {public_url}/sms")
        logger.info(f"Set this URL in your Twilio console for SMS messaging")
        
        # Keep the tunnel alive
        logger.info("Tunnel established. Press Ctrl+C to quit.")
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Closing tunnel...")
            ngrok.disconnect(public_url)
            logger.info("Tunnel closed.")
    
    except Exception as e:
        logger.error(f"Error creating tunnel: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 