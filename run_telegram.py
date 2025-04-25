#!/usr/bin/env python3
"""
Run the Telegram bot in polling mode.
This script starts the Telegram bot using the pyTelegramBotAPI library in polling mode.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure detailed logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("telegram_bot")

def main():
    """Main function to run the Telegram bot"""
    # Load environment variables
    load_dotenv()
    
    # Get Telegram token from environment
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in .env file!")
        logger.error("Please add your bot token to the .env file first.")
        sys.exit(1)
    
    # Print startup banner
    print("\n" + "="*60)
    print("  Telegram Bot Startup".center(60))
    print("="*60)
    print("  Token: " + token[:6] + "..." + token[-4:])  # Show partial token for confirmation
    print("  Bot is starting in polling mode...")
    print("  Press Ctrl+C to stop the bot")
    print("="*60)
    
    try:
        # Import the bot module here to allow environment setup first
        from telegram_bot import run_bot
        
        # Run the bot with polling
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\nGracefully shutting down...\n")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 