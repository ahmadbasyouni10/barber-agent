#!/usr/bin/env python3
import os
import logging
import time
import traceback
from dotenv import load_dotenv
import telebot
from chains.agent import process_incoming_message, CONVERSATION_MEMORY_CACHE

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the bot token from environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_TOKEN:
    logger.error("No TELEGRAM_BOT_TOKEN found in .env file!")
    exit(1)

# Initialize the bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    """Handle /start and /help commands"""
    welcome_text = (
        "👋 Hi there! I'm your Barber Scheduling Assistant.\n\n"
        "I can help you with:\n"
        "• Booking appointments\n"
        "• Checking availability\n"
        "• Rescheduling appointments\n"
        "• Canceling appointments\n"
        "• Viewing your upcoming appointments\n\n"
        "Just let me know what you need in natural language, like:\n"
        "'Book a haircut tomorrow at 3pm'"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Handle all other messages"""
    try:
        # Extract user information
        chat_id = message.chat.id
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        text = message.text
        
        # Create a pseudo phone number using Telegram ID
        phone_number = f"+tg{user_id}"
        
        logger.info(f"Received message from {first_name} (ID: {user_id}, phone: {phone_number})")
        logger.info(f"Message content: '{text}'")
        
        # Debug - log the entire CONVERSATION_MEMORY_CACHE keys
        memory_keys = list(CONVERSATION_MEMORY_CACHE.keys())
        logger.info(f"Current conversation memory keys: {memory_keys}")
        logger.info(f"CONVERSATION_MEMORY_CACHE object ID: {id(CONVERSATION_MEMORY_CACHE)}")
        
        # Check if this is a new or existing conversation
        has_existing_conversation = phone_number in CONVERSATION_MEMORY_CACHE
        if has_existing_conversation:
            # Log details about the existing conversation
            memory = CONVERSATION_MEMORY_CACHE[phone_number]
            chat_history_length = len(memory.chat_memory.messages) if hasattr(memory, 'chat_memory') else 0
            logger.info(f"Found existing conversation for {phone_number} with {chat_history_length} messages in history")
            if chat_history_length > 0 and hasattr(memory, 'chat_memory'):
                logger.info(f"Last message in history: '{memory.chat_memory.messages[-1].content}'")
        else:
            logger.info(f"Starting new conversation for {phone_number} - no previous memory found")
        
        # Process the message using our agent
        logger.info(f"Passing message to agent for processing: '{text}'")
        agent_response = process_incoming_message(phone_number, text)
        
        # Verify the conversation was stored properly after processing
        if phone_number in CONVERSATION_MEMORY_CACHE:
            memory = CONVERSATION_MEMORY_CACHE[phone_number]
            chat_history_length = len(memory.chat_memory.messages) if hasattr(memory, 'chat_memory') else 0
            logger.info(f"After processing: Conversation for {phone_number} has {chat_history_length} messages in history")
            if chat_history_length > 0 and hasattr(memory, 'chat_memory'):
                # Log the last few messages to verify context is maintained
                last_msgs = memory.chat_memory.messages[-min(4, chat_history_length):]
                logger.info(f"Last few messages in history: {[msg.content for msg in last_msgs]}")
        else:
            logger.warning(f"After processing: No conversation memory found for {phone_number}!")
        
        logger.info(f"Agent response: '{agent_response}'")
        
        # Send response back to Telegram
        bot.send_message(chat_id, agent_response)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        logger.error(traceback.format_exc())
        bot.send_message(message.chat.id, "Sorry, I encountered an error. Please try again.")

def run_bot():
    """Run the bot with polling"""
    logger.info("Starting Telegram bot with polling...")
    try:
        # Use a longer timeout and smaller interval for more responsive polling
        bot.polling(none_stop=True, interval=2, timeout=60)
    except Exception as e:
        logger.error(f"Polling error: {e}")
        logger.error(traceback.format_exc())
        time.sleep(15)  # Wait before trying to reconnect

if __name__ == "__main__":
    logger.info("Telegram bot starting...")
    run_bot() 