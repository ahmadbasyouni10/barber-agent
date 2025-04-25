import os
from twilio.rest import Client
from datetime import datetime, timedelta
import logging
from typing import Union, Dict
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Twilio configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')

# Telegram configuration
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
BARBER_TELEGRAM_ID = os.environ.get('BARBER_TELEGRAM_ID', '')  # Telegram ID of the barber
BARBER_BOT_TOKEN = os.environ.get('BARBER_BOT_TOKEN', '')  # Separate bot token for barber notifications

# Track reminders and notifications
scheduled_reminders = {}

# Initialize scheduler (shared with app.py)
scheduler = None

# Initialize Twilio client
try:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    else:
        twilio_client = None
except Exception as e:
    logger.error(f"Error initializing Twilio client: {e}")
    twilio_client = None

def get_twilio_client():
    """Get Twilio client or None if credentials not available."""
    return twilio_client

def send_telegram_message(chat_id: str, message: str, use_barber_bot: bool = False) -> bool:
    """Send a message via Telegram API"""
    # Determine which token to use
    bot_token = BARBER_BOT_TOKEN if use_barber_bot and BARBER_BOT_TOKEN else TELEGRAM_TOKEN
    
    if not bot_token:
        logger.warning(f"Telegram token not found for {'barber bot' if use_barber_bot else 'customer bot'}, can't send Telegram messages")
        return False
    
    # Remove the +tg prefix if present
    if chat_id.startswith('+tg'):
        chat_id = chat_id[3:]
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Telegram message sent to {chat_id} using {'barber bot' if use_barber_bot else 'customer bot'}: {message}")
            return True
        else:
            logger.error(f"Failed to send Telegram message: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False

def send_sms(to_number: str, message: str) -> bool:
    """Send an SMS message using Twilio."""
    if not twilio_client or not TWILIO_PHONE_NUMBER:
        logger.warning("Twilio not configured, skipping SMS send")
        logger.info(f"Would have sent to {to_number}: {message}")
        return False
    
    # Skip if it's a Telegram phone number
    if to_number.startswith("+tg"):
        logger.info(f"Skipping SMS to Telegram user {to_number}")
        return False
    
    try:
        # Real SMS sending
        sms = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number
        )
        logger.info(f"Sent SMS to {to_number}: {message} (SID: {sms.sid})")
        return True
    except TwilioRestException as e:
        logger.error(f"Twilio error: {e}")
        return False
    except Exception as e:
        error_msg = f"Error sending SMS to {to_number}: {str(e)}"
        logger.error(error_msg)
        return False

def send_appointment_reminder(to_number: str, appointment_time: datetime) -> bool:
    """Send a reminder for an upcoming appointment."""
    logger.info(f"Executing reminder for {to_number} for appointment at {appointment_time}")
    formatted_time = appointment_time.strftime("%A, %B %d at %I:%M %p")
    message = f"Reminder: You have a barber appointment tomorrow at {formatted_time}. Reply CONFIRM to confirm or CANCEL to cancel."
    result = send_sms(to_number, message)
    return result

def send_hour_before_reminder(to_number: str, appointment_time: datetime) -> bool:
    """Send a reminder 1 hour before the appointment."""
    logger.info(f"Executing 1-hour reminder for {to_number} for appointment at {appointment_time}")
    formatted_time = appointment_time.strftime("%I:%M %p")
    message = f"Your haircut appointment is in 1 hour at {formatted_time}. We're looking forward to seeing you soon!"
    result = send_sms(to_number, message)
    return result

def schedule_reminders(to_number: str, appointment_time: datetime) -> bool:
    """Schedule reminders for 24 hours and 1 hour before the appointment."""
    try:
        # Calculate when to send the reminders
        reminder_24h = appointment_time - timedelta(hours=24)
        reminder_1h = appointment_time - timedelta(hours=1)
        now = datetime.now()
        
        # Get the global scheduler
        global scheduler
        if scheduler is None:
            from app import scheduler as app_scheduler
            scheduler = app_scheduler
        
        # Schedule the 24-hour reminder if it's in the future
        job_id_24h = f"reminder_24h_{to_number}_{int(appointment_time.timestamp())}"
        if reminder_24h > now:
            logger.info(f"Scheduling 24-hour reminder for {to_number} at {reminder_24h}")
            
            # Remove any existing reminder for this appointment
            for job in scheduler.get_jobs():
                if job.id == job_id_24h:
                    logger.info(f"Removing existing 24h reminder job {job_id_24h}")
                    job.remove()
            
            # Schedule the new 24-hour reminder
            scheduler.add_job(
                send_appointment_reminder,
                'date',
                run_date=reminder_24h,
                args=[to_number, appointment_time],
                id=job_id_24h,
                replace_existing=True
            )
            
            # Track the scheduled reminder
            scheduled_reminders[job_id_24h] = {
                "phone": to_number,
                "appointment_time": appointment_time,
                "reminder_time": reminder_24h,
                "type": "24h reminder",
                "scheduled_at": datetime.now()
            }
        else:
            logger.warning(f"Not scheduling 24h reminder for {to_number} as reminder time {reminder_24h} is in the past")
        
        # Schedule the 1-hour reminder if it's in the future
        job_id_1h = f"reminder_1h_{to_number}_{int(appointment_time.timestamp())}"
        if reminder_1h > now:
            logger.info(f"Scheduling 1-hour reminder for {to_number} at {reminder_1h}")
            
            # Remove any existing reminder for this appointment
            for job in scheduler.get_jobs():
                if job.id == job_id_1h:
                    logger.info(f"Removing existing 1h reminder job {job_id_1h}")
                    job.remove()
            
            # Schedule the new 1-hour reminder
            scheduler.add_job(
                send_hour_before_reminder,
                'date',
                run_date=reminder_1h,
                args=[to_number, appointment_time],
                id=job_id_1h,
                replace_existing=True
            )
            
            # Track the scheduled reminder
            scheduled_reminders[job_id_1h] = {
                "phone": to_number,
                "appointment_time": appointment_time,
                "reminder_time": reminder_1h,
                "type": "1h reminder",
                "scheduled_at": datetime.now()
            }
        else:
            logger.warning(f"Not scheduling 1h reminder for {to_number} as reminder time {reminder_1h} is in the past")
        
        return True
    
    except Exception as e:
        logger.error(f"Error scheduling reminders for {to_number}: {e}")
        return False

def get_scheduled_reminders() -> Dict:
    """Get all currently scheduled reminders."""
    return scheduled_reminders

def notify_barber_of_booking(barber_phone: str, customer_phone: str, appointment_time: datetime, recipient: str = "self") -> bool:
    """Notify the barber about a new booking.
    
    Args:
        barber_phone: The barber's phone number
        customer_phone: The customer's phone number
        appointment_time: The scheduled appointment time
        recipient: Who the appointment is for (default: 'self')
        
    Returns:
        True if the notification was sent successfully, False otherwise
    """
    formatted_time = appointment_time.strftime("%A, %B %d at %I:%M %p")
    
    # Get customer info - could be a phone number or Telegram ID
    if customer_phone.startswith('+tg'):
        customer_info = f"Telegram user {customer_phone.replace('+tg', '')}"
    else:
        customer_info = customer_phone
    
    # Include recipient information if not 'self'
    recipient_info = "" if recipient.lower() == "self" else f" for {recipient}"
    
    # Create the notification message
    message = f"📅 *New Appointment*\nTime: {formatted_time}\nCustomer: {customer_info}{recipient_info}"
    
    # Send via different notification channels
    notification_sent = False
    
    # Try SMS if Twilio is configured
    if twilio_client and TWILIO_PHONE_NUMBER:
        sms_sent = send_sms(barber_phone, message)
        notification_sent = notification_sent or sms_sent
    
    # Try Telegram with regular customer bot if barber's ID is configured
    if BARBER_TELEGRAM_ID:
        telegram_sent = send_telegram_message(BARBER_TELEGRAM_ID, message)
        notification_sent = notification_sent or telegram_sent
    
    # Try dedicated barber bot if configured
    if BARBER_BOT_TOKEN and BARBER_TELEGRAM_ID:
        barber_bot_sent = send_telegram_message(BARBER_TELEGRAM_ID, message, use_barber_bot=True)
        notification_sent = notification_sent or barber_bot_sent
    
    # Log outcome
    if notification_sent:
        logger.info(f"Successfully sent booking notification to barber for appointment at {formatted_time}")
    else:
        logger.warning(f"Failed to send any booking notifications to barber for appointment at {formatted_time}")
    
    return notification_sent

def notify_barber_of_cancellation(barber_phone: str, customer_phone: str, appointment_time: datetime) -> bool:
    """Notify the barber about a cancelled appointment.
    
    Args:
        barber_phone: The barber's phone number
        customer_phone: The customer's phone number
        appointment_time: The scheduled appointment time
        
    Returns:
        True if the notification was sent successfully, False otherwise
    """
    formatted_time = appointment_time.strftime("%A, %B %d at %I:%M %p")
    
    # Create the notification message
    message = f"❌ *Cancelled Appointment*\nTime: {formatted_time}\nCustomer: {customer_phone}"
    
    # Send via different notification channels
    notification_sent = False
    
    # Try SMS if Twilio is configured
    if twilio_client and TWILIO_PHONE_NUMBER:
        sms_sent = send_sms(barber_phone, message)
        notification_sent = notification_sent or sms_sent
    
    # Try Telegram with regular customer bot if barber's ID is configured
    if BARBER_TELEGRAM_ID:
        telegram_sent = send_telegram_message(BARBER_TELEGRAM_ID, message)
        notification_sent = notification_sent or telegram_sent
    
    # Try dedicated barber bot if configured
    if BARBER_BOT_TOKEN and BARBER_TELEGRAM_ID:
        barber_bot_sent = send_telegram_message(BARBER_TELEGRAM_ID, message, use_barber_bot=True)
        notification_sent = notification_sent or barber_bot_sent
    
    return notification_sent

def notify_barber_of_reschedule(barber_phone: str, customer_phone: str, old_time: datetime, new_time: datetime) -> bool:
    """Notify the barber about a rescheduled appointment.
    
    Args:
        barber_phone: The barber's phone number
        customer_phone: The customer's phone number
        old_time: The original appointment time
        new_time: The new appointment time
        
    Returns:
        True if the notification was sent successfully, False otherwise
    """
    old_formatted = old_time.strftime("%A, %B %d at %I:%M %p")
    new_formatted = new_time.strftime("%A, %B %d at %I:%M %p")
    
    # Create the notification message
    message = f"🔄 *Rescheduled Appointment*\n"
    message += f"Customer: {customer_phone}\n"
    message += f"From: {old_formatted}\n"
    message += f"To: {new_formatted}"
    
    # Send via different notification channels
    notification_sent = False
    
    # Try SMS if Twilio is configured
    if twilio_client and TWILIO_PHONE_NUMBER:
        sms_sent = send_sms(barber_phone, message)
        notification_sent = notification_sent or sms_sent
    
    # Try Telegram with regular customer bot if barber's ID is configured
    if BARBER_TELEGRAM_ID:
        telegram_sent = send_telegram_message(BARBER_TELEGRAM_ID, message)
        notification_sent = notification_sent or telegram_sent
    
    # Try dedicated barber bot if configured
    if BARBER_BOT_TOKEN and BARBER_TELEGRAM_ID:
        barber_bot_sent = send_telegram_message(BARBER_TELEGRAM_ID, message, use_barber_bot=True)
        notification_sent = notification_sent or barber_bot_sent
    
    return notification_sent

def send_booking_confirmation(phone_number: str, appointment_time: datetime, service_type: str, appointment_id: str) -> bool:
    """Send a booking confirmation to the customer.
    
    Args:
        phone_number: The customer's phone number
        appointment_time: The scheduled appointment time
        service_type: The type of service booked
        appointment_id: The unique appointment identifier
        
    Returns:
        True if the confirmation was sent successfully, False otherwise
    """
    # Format the date and time nicely
    formatted_time = appointment_time.strftime("%A, %B %d at %I:%M %p")
    
    # Create the confirmation message
    message = f"✅ *Booking Confirmed*\n\nYour {service_type} is scheduled for {formatted_time}.\n\nReference #: {appointment_id}\n\nYou'll receive a reminder 24 hours and 1 hour before your appointment."
    
    # Determine message type based on phone number
    if phone_number.startswith('+tg'):
        # Extract Telegram user ID from phone number
        user_id = phone_number.replace("+tg", "")
        return send_telegram_message(user_id, message)
    else:
        # Send SMS for regular phone numbers
        return send_sms(phone_number, message) 