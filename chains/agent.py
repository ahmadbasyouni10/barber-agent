from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM
from langchain.schema import SystemMessage
from langchain.memory import ConversationBufferMemory
from langchain.tools import tool
import os
import datetime
from typing import Dict, List, Optional, Any
import logging

# Dictionary to store agent memory by phone number
CONVERSATION_MEMORY_CACHE = {}

logger = logging.getLogger(__name__)

from services.appointment_service import (
    book_appointment as book_appt_service,
    cancel_appointment as cancel_appt_service,
    reschedule_appointment as reschedule_appt_service,
    check_availability as check_avail_service,
    get_upcoming_appointments as get_upcoming_service
)

# Define tools for the agent
@tool
def book_appointment(
    phone_number: str, 
    date: str, 
    time: str, 
    service_type: Optional[str] = "haircut",
    recipient: Optional[str] = "self",
    confirmed: Optional[bool] = True,
    customer_name: Optional[str] = ""
) -> str:
    """Book a new appointment for a customer.
    
    Args:
        phone_number: The customer's phone number.
        date: The date for the appointment (e.g. '2023-10-15', 'tomorrow', 'next friday').
        time: The time for the appointment (e.g. '3:00 PM', '15:00').
        service_type: Type of service requested (default: haircut).
        recipient: Who the appointment is for (default: 'self', can be 'brother', 'friend', etc.)
        confirmed: Whether the appointment has been confirmed by the user (default: True).
        customer_name: The customer's name if provided (optional).
        
    Returns:
        A confirmation message about the booking status.
    """
    logger.info(f"Booking appointment for {phone_number} - Date: {date}, Time: {time}, Confirmed: {confirmed}, Customer: {customer_name}")
    
    # Clean up parameters
    if not phone_number or phone_number == "":
        phone_number = "1234567890"  # Default for web testing
    
    # Handle date manually instead of relying on parser
    now = datetime.datetime.now()
    appointment_date = None
    
    # Direct handling of special date formats
    if date.lower() == "tomorrow":
        appointment_date = now + datetime.timedelta(days=1)
    elif date.lower() == "today":
        appointment_date = now
    elif date.lower().startswith("next "):
        # Handle "next monday", "next tuesday", etc.
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day_name in enumerate(day_names):
            if day_name in date.lower():
                days_until = (i - now.weekday()) % 7
                if days_until == 0:  # If it's the same day of week, go to next week
                    days_until = 7
                appointment_date = now + datetime.timedelta(days=days_until)
                break
    else:
        # Try to parse as ISO format
        try:
            if "-" in date:
                parts = date.split("-")
                if len(parts) == 3:
                    year, month, day = map(int, parts)
                    appointment_date = datetime.datetime(year, month, day)
        except:
            pass
    
    # If we couldn't parse the date, use tomorrow as a fallback
    if not appointment_date:
        appointment_date = now + datetime.timedelta(days=1)
        logger.warning(f"Could not parse date '{date}', using tomorrow instead")
    
    # Handle time manually
    appointment_hour = 12  # Default to noon
    appointment_minute = 0
    
    # Simple time parsing
    try:
        # Handle "3:30 PM" format
        if ":" in time:
            time_parts = time.split(":")
            hour = int(time_parts[0])
            minute_part = time_parts[1].lower()
            
            if "pm" in minute_part and hour < 12:
                hour += 12
            elif "am" in minute_part and hour == 12:
                hour = 0
                
            minute = int(''.join(c for c in minute_part if c.isdigit()))
            appointment_hour = hour
            appointment_minute = minute
        # Handle "3pm" format
        elif "pm" in time.lower() or "am" in time.lower():
            numeric_part = ''.join(c for c in time if c.isdigit())
            hour = int(numeric_part)
            
            if "pm" in time.lower() and hour < 12:
                hour += 12
            elif "am" in time.lower() and hour == 12:
                hour = 0
                
            appointment_hour = hour
        # Handle "15:00" 24-hour format
        else:
            if ":" in time:
                hour, minute = map(int, time.split(":"))
                appointment_hour = hour
                appointment_minute = int(minute)
            else:
                appointment_hour = int(time)
    except:
        # Default to noon if parsing fails
        appointment_hour = 12
        appointment_minute = 0
        logger.warning(f"Could not parse time '{time}', using noon instead")
    
    # Construct a datetime object
    appointment_dt = appointment_date.replace(
        hour=appointment_hour, 
        minute=appointment_minute,
        second=0,
        microsecond=0
    )
    
    # Format as string for the API
    formatted_datetime = appointment_dt.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Formatted appointment time: {formatted_datetime}")
    
    # Create the entities dictionary
    entities = {
        'datetime': formatted_datetime,  # Use the pre-formatted datetime string
        'service_type': service_type,
        'recipient': recipient,
        'confirmed': confirmed,
        'customer_name': customer_name
    }
    
    try:
        result = book_appt_service(phone_number, entities)
        return result['message']
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        return f"Sorry, I couldn't book that appointment: {str(e)}"

@tool
def cancel_appointment(phone_number: str, appointment_id: Optional[str] = None) -> str:
    """Cancel an existing appointment.
    
    Args:
        phone_number: The customer's phone number.
        appointment_id: Optional ID of the specific appointment to cancel.
        
    Returns:
        A confirmation message about the cancellation.
    """
    entities = {}
    if appointment_id:
        entities['appointment_id'] = appointment_id
        
    result = cancel_appt_service(phone_number, entities)
    return result['message']

@tool
def reschedule_appointment(
    phone_number: str, 
    new_date: str, 
    new_time: str, 
    appointment_id: Optional[str] = None
) -> str:
    """Reschedule an existing appointment to a new date/time.
    
    Args:
        phone_number: The customer's phone number.
        new_date: The new date for the appointment.
        new_time: The new time for the appointment.
        appointment_id: Optional ID of the specific appointment to reschedule.
        
    Returns:
        A confirmation message about the rescheduling.
    """
    entities = {
        'date': new_date,
        'time': new_time
    }
    if appointment_id:
        entities['appointment_id'] = appointment_id
        
    result = reschedule_appt_service(phone_number, entities)
    return result['message']

@tool
def check_availability(date: str, service_type: Optional[str] = "haircut") -> str:
    """Check available time slots on a given date.
    
    Args:
        date: The date to check availability for.
        service_type: Type of service requested (default: haircut).
        
    Returns:
        A string listing the available time slots.
    """
    return check_avail_service(date)

@tool
def get_upcoming_appointments(phone_number: str) -> str:
    """Get all upcoming appointments for a customer.
    
    Args:
        phone_number: The customer's phone number.
        
    Returns:
        A string listing the customer's upcoming appointments.
    """
    return get_upcoming_service(phone_number)

def create_barber_agent(memory=None, phone_number=None):
    """Create a LangChain agent for the barber scheduling system."""
    # Define the tools the agent can use
    tools = [
        book_appointment,
        cancel_appointment,
        reschedule_appointment,
        check_availability,
        get_upcoming_appointments
    ]
    
    # Create a chat model - use OpenAI by default since Ollama doesn't fully support functions
    # Only try Ollama if explicitly requested via environment variable
    use_ollama = os.environ.get("USE_OLLAMA", "false").lower() == "true"
    
    if use_ollama:
        try:
            # Try to use Ollama with a local model (assumes Ollama is running)
            llm = OllamaLLM(model="llama2")
            print("Using Ollama for agent")
        except Exception as e:
            print(f"Error initializing Ollama: {e}")
            print("Falling back to OpenAI...")
            llm = ChatOpenAI(temperature=0)
    else:
        # Use OpenAI by default
        llm = ChatOpenAI(temperature=0)  # Zero temperature for more consistent responses
    
    # Create a system message that explains what the agent does
    system_message = """You are a friendly and helpful AI assistant for Stellar Cuts Barber Shop. 
Your name is Stella.

Your main job is to help customers:
- Book new haircut appointments
- Cancel or reschedule existing appointments
- Check barber availability
- View their upcoming appointments

IMPORTANT GUIDELINES:

1. Be warm and personable in your responses. Use a friendly, conversational tone.
2. ALWAYS confirm appointment details before booking. When a customer wants to book, 
   respond with "I'll book your appointment for [DATE] at [TIME]. Is that correct?" 
   and wait for their confirmation before proceeding.
3. If the requested time is unavailable, offer specific alternatives.
4. Provide complete information in your responses.
5. Handle date expressions like "tomorrow", "next Friday", "in 2 days", etc.
6. If you get stuck in a loop or can't find availability, suggest booking at a different time 
   rather than repeatedly searching for available slots.
7. Properly handle conversational follow-ups like "thank you", "yes", "no", or other short responses.
   Maintain the context of previous messages when responding to these.
8. When a customer responds with "yes", "yeah", "sure", "ok", "correct", or any affirmative response
   after you've asked about booking details, ALWAYS proceed with the booking by calling the book_appointment
   tool with the date and time you previously confirmed with them. DO NOT ask for the date and time again.
9. If a customer says "no" after your confirmation question, ask for their preferred alternative time.
10. If a customer tries to book an appointment when they already have one, check if the appointment is 
    for someone else (like "for my brother" or "for my friend"). If so, treat it as a separate booking
    and don't suggest rescheduling the existing appointment.
11. When a customer indicates the appointment is for someone else, capture who it's for in the "recipient" entity.
    For example, if they say "book for my brother", set recipient="brother".

CUSTOMER INFORMATION:
- Always ask for the customer's name if it's their first time booking and you don't already know it.
- Use their name in your responses when appropriate to personalize the conversation.
- Store the customer's name with the appointment for future reference.
- If the customer has booked before and you know their name, greet them by name.

CONFIRMATION HANDLING:
- If your last message asked "Would you like me to book your appointment for [DATE] at [TIME]?" 
  and the customer responds with a simple "yes", proceed with booking exactly that time.
- If your most recent message was asking for confirmation of a specific date and time, and the user
  responds with any affirmative message (yes, yeah, sure, ok, correct), IMMEDIATELY proceed with booking
  without asking for any more information.
- NEVER ask for date/time again after a user confirms with "yes" or similar affirmative responses.

BOOKING FOR OTHERS:
- When a customer mentions booking for someone else (e.g., "for my brother", "for my friend"), 
  recognize this is a different appointment and don't treat it as a conflict with their own appointments.
- Ask for the name of the person if needed for clarity.
- Include the recipient's name in your responses and confirmations.

HOURS AND SERVICES:
- Open Monday-Saturday, 10:00 AM to 6:00 PM
- Closed on Sundays
- Services: haircuts, beard trims, styling, and shaves

BOOKING PRACTICES:
- Appointments are available in 30-minute increments
- Haircuts typically take 30 minutes
- We recommend booking at least a day in advance for preferred times

The shop is located at 123 Main Street, and walk-ins are welcome but appointments get priority.

Always try to understand what the customer needs, even if they don't express it perfectly.
Treat each response as part of an ongoing conversation, not as isolated requests.
"""

    # Add phone number context if provided
    if phone_number:
        system_message += f"\n\nCURRENT CUSTOMER:\nPhone: {phone_number}"
    
    # Create a prompt for the agent
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_message),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])
    
    # Create memory for the agent if not provided
    if memory is None:
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    # Create the agent
    agent = create_openai_functions_agent(llm, tools, prompt)
    
    # Create an agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True
    )
    
    return agent_executor

def process_incoming_message(sender_phone: str, message_text: str) -> str:
    """Process an incoming message and return a response."""
    # Get or create memory for this conversation
    if sender_phone not in CONVERSATION_MEMORY_CACHE:
        logger.info(f"Creating new conversation memory for {sender_phone}")
        CONVERSATION_MEMORY_CACHE[sender_phone] = ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True
        )
    else:
        logger.info(f"Using existing conversation memory for {sender_phone}")
        # Log the existing conversation history for debugging
        memory = CONVERSATION_MEMORY_CACHE[sender_phone]
        if hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
            msg_count = len(memory.chat_memory.messages)
            logger.info(f"Existing memory has {msg_count} messages")
            if msg_count > 0:
                # Log a preview of the existing conversation
                last_msgs = memory.chat_memory.messages[-min(4, msg_count):]
                logger.info(f"Last messages in history: {[msg.content for msg in last_msgs]}")
    
    memory = CONVERSATION_MEMORY_CACHE[sender_phone]
    
    # Handle short responses like "yes", "no" with special context preservation
    if message_text.lower() in ["yes", "yeah", "sure", "ok", "okay", "correct"]:
        logger.info("Detected affirmative response, maintaining booking context")
    
    # Create an agent with the existing memory and the sender's phone number
    agent = create_barber_agent(memory=memory, phone_number=sender_phone)
    
    # Use the LangSmith tracing to visualize the agent's thinking
    os.environ["LANGSMITH_TRACING"] = "true"
    
    # Get existing appointments for this user
    try:
        # Check for existing appointments to include in context
        from services.appointment_service import get_upcoming_appointments as get_upcoming_appts_raw
        upcoming_appts = get_upcoming_appts_raw(sender_phone)
        if upcoming_appts and "No upcoming appointments" not in upcoming_appts:
            logger.info(f"User has existing appointments: {upcoming_appts}")
    except Exception as e:
        logger.warning(f"Error checking for existing appointments: {e}")
    
    # Prepare input - make sure we only pass a single input parameter
    agent_input = {"input": message_text}
    
    # Run the agent on the message
    try:
        logger.info(f"Running agent with memory object ID: {id(memory)} for {sender_phone}")
        response = agent.invoke(agent_input)
        
        # Confirm memory was updated after processing
        if hasattr(memory, 'chat_memory') and memory.chat_memory.messages:
            msg_count = len(memory.chat_memory.messages)
            logger.info(f"After processing: memory has {msg_count} messages")
            # Ensure the updated memory is saved in the cache
            CONVERSATION_MEMORY_CACHE[sender_phone] = memory
            logger.info(f"Updated memory in cache for {sender_phone}")
            
        # Return the agent's response
        return response["output"]
    except Exception as e:
        import traceback
        logger.error(f"Error in agent: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Sorry, I encountered an error: {str(e)}" 